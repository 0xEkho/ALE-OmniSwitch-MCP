"""
DHCP Relay parsers for OmniSwitch AOS.

Parses output from:
- show ip dhcp relay interface
- show ip dhcp relay statistics
- show ip dhcp relay counters
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional


def parse_show_dhcp_relay_interface(output: str) -> List[Dict[str, Any]]:
    """
    Parse 'show ip dhcp relay interface' command output.
    
    Returns DHCP relay configuration per interface.
    """
    interfaces = []
    
    lines = output.strip().split('\n')
    current_interface = None
    
    for line in lines:
        # Interface line: "Interface: vlan 100"
        if_match = re.search(r'Interface:\s*(\S+(?:\s+\d+)?)', line, re.IGNORECASE)
        if if_match:
            if current_interface:
                interfaces.append(current_interface)
            
            current_interface = {
                "interface": if_match.group(1),
                "admin_state": None,
                "oper_state": None,
                "servers": [],
                "agent_information": False,
                "statistics": {}
            }
            continue
        
        if current_interface:
            # Admin state
            if "Admin State:" in line or "Administrative State:" in line:
                match = re.search(r'State:\s*(enabled|disabled)', line, re.IGNORECASE)
                if match:
                    current_interface["admin_state"] = match.group(1).lower()
            
            # Operational state
            if "Oper State:" in line or "Operational State:" in line:
                match = re.search(r'State:\s*(up|down)', line, re.IGNORECASE)
                if match:
                    current_interface["oper_state"] = match.group(1).lower()
            
            # Server IP
            server_match = re.search(r'Server:\s*(\d+\.\d+\.\d+\.\d+)', line, re.IGNORECASE)
            if server_match:
                current_interface["servers"].append(server_match.group(1))
            
            # Agent information option 82
            if "Agent Information:" in line or "Option 82:" in line:
                if re.search(r'enabled|yes', line, re.IGNORECASE):
                    current_interface["agent_information"] = True
    
    # Add last interface
    if current_interface:
        interfaces.append(current_interface)
    
    return interfaces


def parse_show_dhcp_relay_statistics(output: str) -> Dict[str, Any]:
    """
    Parse 'show ip dhcp relay statistics' command output.
    
    Returns DHCP relay packet statistics.
    """
    stats = {
        "requests_received": 0,
        "requests_forwarded": 0,
        "requests_dropped": 0,
        "replies_received": 0,
        "replies_forwarded": 0,
        "replies_dropped": 0,
        "total_packets": 0,
        "errors": 0
    }
    
    lines = output.strip().split('\n')
    
    for line in lines:
        # Reception From Client: Total Count = 13371
        client_match = re.search(r'Reception From Client.*Total Count\s*=\s*(\d+)', line, re.IGNORECASE)
        if client_match:
            stats["requests_received"] = int(client_match.group(1))
        
        # Tx Server: Total Count = 1062 (forwarded to server)
        tx_match = re.search(r'Tx Server.*Total Count\s*=\s*(\d+)', line, re.IGNORECASE)
        if tx_match:
            stats["requests_forwarded"] += int(tx_match.group(1))
        
        # Forw Delay Violation, Max Hops Violation, etc. = drops
        drop_match = re.search(r'(Forw Delay|Max Hops|Agent Info|Invalid Gateway).*Total Count\s*=\s*(\d+)', line, re.IGNORECASE)
        if drop_match and int(drop_match.group(2)) > 0:
            stats["requests_dropped"] += int(drop_match.group(2))
            stats["errors"] += int(drop_match.group(2))
        
        # Standard format fallback
        match = re.search(r'Requests?\s+Received:\s*(\d+)', line, re.IGNORECASE)
        if match:
            stats["requests_received"] = int(match.group(1))
        
        match = re.search(r'Requests?\s+Forwarded:\s*(\d+)', line, re.IGNORECASE)
        if match:
            stats["requests_forwarded"] = int(match.group(1))
        
        match = re.search(r'Requests?\s+Dropped:\s*(\d+)', line, re.IGNORECASE)
        if match:
            stats["requests_dropped"] = int(match.group(1))
        
        match = re.search(r'Replies\s+Received:\s*(\d+)', line, re.IGNORECASE)
        if match:
            stats["replies_received"] = int(match.group(1))
        
        match = re.search(r'Replies\s+Forwarded:\s*(\d+)', line, re.IGNORECASE)
        if match:
            stats["replies_forwarded"] = int(match.group(1))
        
        match = re.search(r'Replies\s+Dropped:\s*(\d+)', line, re.IGNORECASE)
        if match:
            stats["replies_dropped"] = int(match.group(1))
        
        match = re.search(r'Errors?:\s*(\d+)', line, re.IGNORECASE)
        if match:
            stats["errors"] += int(match.group(1))
    
    # Calculate totals
    stats["total_packets"] = (
        stats["requests_received"] + stats["replies_received"]
    )
    
    return stats


def parse_show_dhcp_relay_counters(output: str) -> Dict[str, Dict[str, int]]:
    """
    Parse 'show ip dhcp relay counters' command output.
    
    Returns detailed DHCP packet counters per interface.
    """
    counters = {}
    
    lines = output.strip().split('\n')
    current_interface = None
    
    for line in lines:
        # Interface identifier
        if_match = re.search(r'(vlan\s+\d+|[\w/]+):', line, re.IGNORECASE)
        if if_match:
            current_interface = if_match.group(1).strip()
            counters[current_interface] = {
                "discover": 0,
                "offer": 0,
                "request": 0,
                "ack": 0,
                "nak": 0,
                "release": 0,
                "inform": 0,
                "decline": 0
            }
            continue
        
        if current_interface:
            # DHCP message types
            for msg_type in ["discover", "offer", "request", "ack", "nak", 
                            "release", "inform", "decline"]:
                match = re.search(rf'{msg_type}:\s*(\d+)', line, re.IGNORECASE)
                if match:
                    counters[current_interface][msg_type.lower()] = int(match.group(1))
    
    return counters


def analyze_dhcp_relay(interfaces: List[Dict[str, Any]], 
                       stats: Dict[str, Any]) -> List[str]:
    """
    Analyze DHCP relay configuration and statistics to detect issues.
    
    Returns list of detected issues.
    """
    issues = []
    
    # Check if relay is configured
    if not interfaces:
        issues.append("No DHCP relay interfaces configured")
        return issues
    
    # Check each interface
    for iface in interfaces:
        iface_name = iface.get("interface", "unknown")
        
        # Admin enabled but oper down
        if iface.get("admin_state") == "enabled" and iface.get("oper_state") == "down":
            issues.append(f"{iface_name}: DHCP relay enabled but interface down")
        
        # No servers configured
        if not iface.get("servers"):
            issues.append(f"{iface_name}: No DHCP servers configured")
        
        # Check statistics if available
        iface_stats = iface.get("statistics", {})
        
        # High drop rate
        req_rcv = iface_stats.get("requests_received", 0)
        req_drop = iface_stats.get("requests_dropped", 0)
        if req_rcv > 0:
            drop_rate = (req_drop / req_rcv) * 100
            if drop_rate > 5:
                issues.append(
                    f"{iface_name}: High DHCP packet drop rate ({drop_rate:.1f}%)"
                )
    
    # Global statistics analysis
    if stats:
        # Calculate overall drop rate
        total_req = stats.get("requests_received", 0)
        total_drop = stats.get("requests_dropped", 0) + stats.get("replies_dropped", 0)
        
        if total_req > 0:
            overall_drop_rate = (total_drop / total_req) * 100
            if overall_drop_rate > 5:
                issues.append(
                    f"Global DHCP drop rate high: {overall_drop_rate:.1f}%"
                )
        
        # Check for errors
        errors = stats.get("errors", 0)
        if errors > 0:
            issues.append(f"DHCP relay errors detected: {errors}")
        
        # Check if forwarding is happening
        req_fwd = stats.get("requests_forwarded", 0)
        rep_fwd = stats.get("replies_forwarded", 0)
        if total_req > 100 and (req_fwd == 0 or rep_fwd == 0):
            issues.append("DHCP packets received but not forwarded - check server connectivity")
    
    return issues
