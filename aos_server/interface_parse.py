"""Parsers for AOS interface-related commands."""
from __future__ import annotations

import re
from typing import Dict


def parse_show_interfaces_detailed(output: str, port_id: str) -> Dict[str, any]:
    """
    Parse 'show interfaces X' output (detailed single port view with stats).
    
    Extracts: interface_type, sfp_type, mac_address, statistics
    """
    result = {
        "port_id": port_id,
        "interface_type": None,
        "sfp_type": None,
        "mac_address": None,
        "statistics": {}
    }
    
    # Parse interface type (Copper/Fiber)
    iface_type_match = re.search(r'Interface Type\s*:\s*(\w+)', output, re.IGNORECASE)
    if iface_type_match:
        result["interface_type"] = iface_type_match.group(1)
    
    # Parse SFP/XFP type
    sfp_match = re.search(r'SFP/XFP\s*:\s*(.+?),', output, re.IGNORECASE)
    if sfp_match:
        sfp_val = sfp_match.group(1).strip()
        if sfp_val != "N/A":
            result["sfp_type"] = sfp_val
    
    # Parse MAC address
    mac_match = re.search(r'MAC address\s*:\s*([0-9a-f:]+)', output, re.IGNORECASE)
    if mac_match:
        result["mac_address"] = mac_match.group(1)
    
    # Parse statistics
    stats = {}
    
    # RX stats
    rx_bytes_match = re.search(r'Bytes Received\s*:\s*(\d+)', output)
    if rx_bytes_match:
        stats["rx_bytes"] = int(rx_bytes_match.group(1))
    
    rx_unicast_match = re.search(r'Rx.*?Unicast Frames\s*:\s*(\d+)', output, re.DOTALL)
    if rx_unicast_match:
        stats["rx_unicast"] = int(rx_unicast_match.group(1))
    
    rx_broadcast_match = re.search(r'Rx.*?Broadcast Frames:\s*(\d+)', output, re.DOTALL)
    if rx_broadcast_match:
        stats["rx_broadcast"] = int(rx_broadcast_match.group(1))
    
    rx_mcast_match = re.search(r'Rx.*?M-cast Frames\s*:\s*(\d+)', output, re.DOTALL)
    if rx_mcast_match:
        stats["rx_multicast"] = int(rx_mcast_match.group(1))
    
    rx_err_match = re.search(r'Rx.*?Error Frames\s*:\s*(\d+)', output, re.DOTALL)
    if rx_err_match:
        stats["rx_errors"] = int(rx_err_match.group(1))
    
    # TX stats
    tx_bytes_match = re.search(r'Bytes Xmitted\s*:\s*(\d+)', output)
    if tx_bytes_match:
        stats["tx_bytes"] = int(tx_bytes_match.group(1))
    
    tx_unicast_match = re.search(r'Tx.*?Unicast Frames\s*:\s*(\d+)', output, re.DOTALL)
    if tx_unicast_match:
        stats["tx_unicast"] = int(tx_unicast_match.group(1))
    
    tx_broadcast_match = re.search(r'Tx.*?Broadcast Frames:\s*(\d+)', output, re.DOTALL)
    if tx_broadcast_match:
        stats["tx_broadcast"] = int(tx_broadcast_match.group(1))
    
    tx_mcast_match = re.search(r'Tx.*?M-cast Frames\s*:\s*(\d+)', output, re.DOTALL)
    if tx_mcast_match:
        stats["tx_multicast"] = int(tx_mcast_match.group(1))
    
    tx_err_match = re.search(r'Tx.*?Error Frames\s*:\s*(\d+)', output, re.DOTALL)
    if tx_err_match:
        stats["tx_errors"] = int(tx_err_match.group(1))
    
    if stats:
        result["statistics"] = stats
    
    return result


def parse_interfaces_status(output: str) -> Dict[str, Dict[str, str]]:
    """
    Parse 'show interfaces status' output.
    
    Returns dict keyed by port_id with detected values.
    """
    interfaces = {}
    
    # Skip header lines
    lines = output.strip().split('\n')
    in_data = False
    
    for line in lines:
        # Detect data section start (line with dashes)
        if '-------' in line:
            in_data = True
            continue
        
        if not in_data:
            continue
        
        # Parse data lines
        # Format: 1/1/4       en    en    1000   Full     -     DIS   Auto    Auto     -    AUTO  en   dis
        match = re.match(
            r'\s*(\d+/\d+/\d+)\s+'  # Port ID
            r'(\S+)\s+'              # Admin Status
            r'(\S+)\s+'              # Auto Nego
            r'(\S+)\s+'              # Speed (detected)
            r'(\S+)',                # Duplex (detected)
            line
        )
        
        if match:
            port_id = match.group(1)
            admin = match.group(2)
            auto_neg = match.group(3)
            speed = match.group(4)
            duplex = match.group(5)
            
            # Determine operational state from speed
            # If speed is '-', port is down
            oper_state = "up" if speed != '-' else "down"
            
            interfaces[port_id] = {
                "port_id": port_id,
                "admin_state": "enabled" if admin == "en" else "disabled",
                "auto_neg": auto_neg == "en",
                "speed": None if speed == '-' else f"{speed}Mbps" if speed.isdigit() else speed,
                "duplex": None if duplex == '-' else duplex,
                "oper_state": oper_state
            }
    
    return interfaces
