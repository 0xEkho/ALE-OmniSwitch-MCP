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


def parse_show_dhcp_relay_interface(output: str) -> Dict[str, Any]:
    """
    Parse 'show ip dhcp relay interface' command output.
    
    Returns DHCP relay configuration including global settings and per-interface mappings.
    
    Example output:
    IP DHCP Relay :
      DHCP Relay Admin Status        = Enable,
      Forward Delay(seconds)         = 0,
      Max number of hops             = 16,
      Relay Agent Information        = Disabled,
      ...
      From Interface VLAN-0100 to Server 10.0.1.50
      From Interface VLAN-0100 to Server 10.0.1.51
    """
    result = {
        "admin_status": "disabled",
        "forward_delay": 0,
        "max_hops": 16,
        "agent_information": False,
        "pxe_support": False,
        "relay_mode": "unknown",
        "interfaces": []
    }
    
    lines = output.strip().split('\n')
    interfaces_map = {}  # Group servers by interface
    
    for line in lines:
        line_stripped = line.strip()
        
        # Global admin status
        if "Admin Status" in line:
            if re.search(r'=\s*(Enable|Enabled)', line, re.IGNORECASE):
                result["admin_status"] = "enabled"
            else:
                result["admin_status"] = "disabled"
        
        # Forward delay
        delay_match = re.search(r'Forward Delay.*=\s*(\d+)', line, re.IGNORECASE)
        if delay_match:
            result["forward_delay"] = int(delay_match.group(1))
        
        # Max hops
        hops_match = re.search(r'Max.*hops.*=\s*(\d+)', line, re.IGNORECASE)
        if hops_match:
            result["max_hops"] = int(hops_match.group(1))
        
        # Agent information (Option 82)
        if "Agent Information" in line or "Relay Agent Information" in line:
            if re.search(r'=\s*(Enable|Enabled)', line, re.IGNORECASE):
                result["agent_information"] = True
        
        # PXE support
        if "PXE" in line:
            if re.search(r'=\s*(Enable|Enabled)', line, re.IGNORECASE):
                result["pxe_support"] = True
        
        # Relay mode
        if "Relay Mode" in line:
            mode_match = re.search(r'=\s*(.+?)(?:,|$)', line)
            if mode_match:
                result["relay_mode"] = mode_match.group(1).strip()
        
        # Per-interface relay: "From Interface VLAN-0100 to Server 10.0.1.50"
        iface_match = re.search(r'From Interface\s+(\S+)\s+to Server\s+(\d+\.\d+\.\d+\.\d+)', line, re.IGNORECASE)
        if iface_match:
            iface_name, server_ip = iface_match.groups()
            if iface_name not in interfaces_map:
                interfaces_map[iface_name] = {
                    "interface": iface_name,
                    "servers": [],
                    "admin_state": "enabled"  # If listed, it's enabled
                }
            interfaces_map[iface_name]["servers"].append(server_ip)
    
    # Convert interfaces map to list
    result["interfaces"] = list(interfaces_map.values())
    
    return result


def parse_show_dhcp_relay_counters(output: str) -> Dict[str, Any]:
    """
    Parse 'show ip dhcp relay counters' command output.
    
    Returns DHCP packet counters by message type.
    
    Example output:
    DHCP Packets:
    DHCP Discover Packets                          : 11467589,
    DHCP Offer Packets                             : 2584497,
    DHCP Request Packets                           : 23010116,
    DHCP ACK Packets                               : 10848485,
    DHCP NACK Packets                              : 755693,
    DHCP Release Packets                           : 215,
    DHCP Decline Packets                           : 628,
    DHCP Inform Packets                            : 131917,
    """
    counters = {
        "discover": 0,
        "offer": 0,
        "request": 0,
        "ack": 0,
        "nack": 0,
        "release": 0,
        "decline": 0,
        "inform": 0,
        "renew": 0,
        "total_client_requests": 0,
        "total_server_responses": 0
    }
    
    for line in output.split('\n'):
        # Match "DHCP <Type> Packets : <count>"
        match = re.search(r'DHCP\s+(\w+)\s+Packets?\s*:\s*(\d+)', line, re.IGNORECASE)
        if match:
            pkt_type = match.group(1).lower()
            count = int(match.group(2))
            
            if pkt_type == "discover":
                counters["discover"] = count
            elif pkt_type == "offer":
                counters["offer"] = count
            elif pkt_type == "request":
                counters["request"] = count
            elif pkt_type == "ack":
                counters["ack"] = count
            elif pkt_type == "nack":
                counters["nack"] = count
            elif pkt_type == "release":
                counters["release"] = count
            elif pkt_type == "decline":
                counters["decline"] = count
            elif pkt_type == "inform":
                counters["inform"] = count
            elif pkt_type == "renew":
                counters["renew"] = count
    
    # Calculate totals
    counters["total_client_requests"] = (
        counters["discover"] + counters["request"] + 
        counters["release"] + counters["decline"] + counters["inform"]
    )
    counters["total_server_responses"] = (
        counters["offer"] + counters["ack"] + counters["nack"]
    )
    
    return counters


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


def analyze_dhcp_relay(relay_config: Dict[str, Any], 
                       counters: Dict[str, Any]) -> List[str]:
    """
    Analyze DHCP relay configuration and counters to detect issues.
    
    Returns list of detected issues.
    """
    issues = []
    
    # Check if relay is enabled
    if relay_config.get("admin_status") != "enabled":
        issues.append("DHCP Relay is disabled")
        return issues
    
    interfaces = relay_config.get("interfaces", [])
    
    # Check if any interfaces configured
    if not interfaces:
        issues.append("DHCP Relay enabled but no interfaces configured")
        return issues
    
    # Check each interface has servers
    for iface in interfaces:
        iface_name = iface.get("interface", "unknown")
        if not iface.get("servers"):
            issues.append(f"{iface_name}: No DHCP servers configured")
    
    # Analyze counters if available
    if counters:
        # Check for high NACK rate (indicates IP exhaustion or config issues)
        ack = counters.get("ack", 0)
        nack = counters.get("nack", 0)
        if ack > 0 and nack > 0:
            nack_rate = (nack / (ack + nack)) * 100
            if nack_rate > 5:
                issues.append(f"High DHCP NACK rate: {nack_rate:.1f}% - check IP pool exhaustion")
        
        # Check for decline packets (duplicate IP issues)
        decline = counters.get("decline", 0)
        if decline > 100:
            issues.append(f"DHCP Decline packets: {decline} - possible duplicate IP conflicts")
        
        # Check request to offer ratio
        discover = counters.get("discover", 0)
        offer = counters.get("offer", 0)
        if discover > 1000 and offer > 0:
            offer_rate = (offer / discover) * 100
            if offer_rate < 90:
                issues.append(f"Low DHCP offer rate: {offer_rate:.1f}% - server may be unreachable")
    
    return issues
