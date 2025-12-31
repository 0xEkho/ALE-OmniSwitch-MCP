"""
NTP (Network Time Protocol) parsers for OmniSwitch AOS.

Parses output from:
- show ntp status
- show ntp client
- show ntp client server-list
- show ntp peers
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional


def parse_show_ntp_status(output: str) -> Dict[str, Any]:
    """
    Parse 'show ntp status' command output.
    
    Returns NTP synchronization status and configuration.
    """
    result = {
        "synchronized": False,
        "mode": "unknown",
        "stratum": None,
        "reference_clock": None,
        "reference_time": None,
        "offset_ms": None,
        "root_delay_ms": None,
        "root_dispersion_ms": None
    }
    
    lines = output.strip().split('\n')
    
    for line in lines:
        # Synchronization status
        if re.search(r'synchronized|sync.*yes|status.*synchronized', line, re.IGNORECASE):
            result["synchronized"] = True
        
        if re.search(r'not.*synchronized|sync.*no', line, re.IGNORECASE):
            result["synchronized"] = False
        
        # Mode (client/server/peer)
        if "Mode:" in line:
            match = re.search(r'Mode:\s*(client|server|peer|broadcast)', line, re.IGNORECASE)
            if match:
                result["mode"] = match.group(1).lower()
        
        # Stratum
        if "Stratum:" in line:
            match = re.search(r'Stratum:\s*(\d+)', line)
            if match:
                result["stratum"] = int(match.group(1))
        
        # Reference clock
        if "Reference Clock:" in line or "Reference:" in line:
            match = re.search(r':\s*(\d+\.\d+\.\d+\.\d+)', line)
            if match:
                result["reference_clock"] = match.group(1)
        
        # Offset
        if "Offset:" in line:
            match = re.search(r'Offset:\s*([-\d.]+)\s*ms', line, re.IGNORECASE)
            if match:
                result["offset_ms"] = float(match.group(1))
        
        # Root delay
        if "Root Delay:" in line:
            match = re.search(r':\s*([\d.]+)\s*ms', line, re.IGNORECASE)
            if match:
                result["root_delay_ms"] = float(match.group(1))
        
        # Root dispersion
        if "Root Dispersion:" in line:
            match = re.search(r':\s*([\d.]+)\s*ms', line, re.IGNORECASE)
            if match:
                result["root_dispersion_ms"] = float(match.group(1))
    
    return result


def parse_show_ntp_client_server_list(output: str) -> List[Dict[str, Any]]:
    """
    Parse 'show ntp client server-list' command output.
    
    Returns list of configured NTP servers with their status.
    """
    servers = []
    
    lines = output.strip().split('\n')
    
    for line in lines:
        # Format: Server IP      Status        Stratum  Delay(ms)  Reachability  Preferred
        # Example: 10.1.0.200    synchronized  2        2.5        255           *
        match = re.search(
            r'(\d+\.\d+\.\d+\.\d+)\s+'                    # IP address
            r'(synchronized|reachable|unreachable|inactive)\s+'  # Status
            r'(\d+)\s+'                                   # Stratum
            r'([\d.]+)\s+'                               # Delay
            r'(\d+)\s*'                                  # Reachability
            r'(\*)?',                                    # Preferred marker
            line,
            re.IGNORECASE
        )
        
        if match:
            ip, status, stratum, delay, reach, preferred = match.groups()
            
            server = {
                "ip": ip,
                "status": status.lower(),
                "stratum": int(stratum),
                "delay_ms": float(delay),
                "reachability": int(reach),
                "preferred": preferred == "*"
            }
            
            servers.append(server)
    
    return servers


def parse_show_ntp_peers(output: str) -> List[Dict[str, Any]]:
    """
    Parse 'show ntp peers' command output.
    
    Returns list of NTP peer associations.
    """
    peers = []
    
    lines = output.strip().split('\n')
    
    for line in lines:
        # Peer format (various possible formats)
        # Example: * 10.1.0.200  .GPS.  2  64  377  2.5  0.125  0.250
        match = re.search(
            r'([*+\-x\s])\s*'                           # Selection indicator
            r'(\d+\.\d+\.\d+\.\d+)\s+'                  # IP address
            r'([\w.]+)\s+'                              # Reference ID
            r'(\d+)\s+'                                 # Stratum
            r'(\d+)\s+'                                 # Poll interval
            r'(\d+)\s+'                                 # Reach
            r'([\d.]+)\s*'                             # Delay
            r'([\d.]+)?\s*'                            # Offset (optional)
            r'([\d.]+)?',                              # Jitter (optional)
            line
        )
        
        if match:
            sel, ip, ref_id, stratum, poll, reach, delay, offset, jitter = match.groups()
            
            # Decode selection indicator
            status_map = {
                '*': 'synchronized',
                '+': 'candidate',
                '-': 'outlier',
                'x': 'falseticker',
                ' ': 'rejected'
            }
            
            peer = {
                "ip": ip,
                "status": status_map.get(sel.strip(), 'unknown'),
                "reference_id": ref_id,
                "stratum": int(stratum),
                "poll_interval": int(poll),
                "reachability": int(reach),
                "delay_ms": float(delay),
                "offset_ms": float(offset) if offset else None,
                "jitter_ms": float(jitter) if jitter else None
            }
            
            peers.append(peer)
    
    return peers


def analyze_ntp_status(ntp_status: Dict[str, Any], servers: List[Dict[str, Any]]) -> List[str]:
    """
    Analyze NTP status and server list to detect issues.
    
    Returns list of detected issues.
    """
    issues = []
    
    # Check synchronization
    if not ntp_status.get("synchronized"):
        issues.append("NTP not synchronized - time may be inaccurate")
    
    # Check stratum (should be < 16)
    stratum = ntp_status.get("stratum")
    if stratum and stratum >= 16:
        issues.append(f"NTP stratum {stratum} invalid (should be < 16)")
    
    # Check servers
    if not servers:
        issues.append("No NTP servers configured")
    else:
        # Check for unreachable servers
        unreachable = [s for s in servers if s.get("status") == "unreachable"]
        if unreachable:
            for srv in unreachable:
                issues.append(f"NTP server {srv['ip']} unreachable")
        
        # Check if any server is synchronized
        synced = [s for s in servers if s.get("status") == "synchronized"]
        if not synced and ntp_status.get("synchronized"):
            issues.append("Synchronized but no server in 'synchronized' state")
        
        # Check reachability (255 = all polls successful)
        low_reach = [s for s in servers if s.get("reachability", 0) < 128]
        for srv in low_reach:
            issues.append(
                f"NTP server {srv['ip']} has low reachability "
                f"({srv['reachability']}/255 polls successful)"
            )
        
        # Check for high delay
        high_delay = [s for s in servers if s.get("delay_ms", 0) > 100]
        for srv in high_delay:
            issues.append(
                f"NTP server {srv['ip']} has high delay ({srv['delay_ms']}ms)"
            )
    
    # Check offset (should be < 100ms ideally)
    offset = ntp_status.get("offset_ms")
    if offset and abs(offset) > 100:
        issues.append(f"NTP offset high: {offset}ms (should be < 100ms)")
    
    return issues
