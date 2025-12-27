"""Parsers for AOS interface-related commands."""
from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple


def parse_show_interfaces_all_detailed(output: str) -> Dict[str, Dict[str, any]]:
    """
    Parse 'show interfaces' output (all ports, detailed format).
    
    Returns dict keyed by port_id with detailed info for each port.
    """
    ports_data = {}
    
    # Split by port sections (each starts with "Chassis/Slot/Port")
    port_sections = re.split(r'(?=Chassis/Slot/Port)', output)
    
    for section in port_sections:
        if not section.strip() or 'Chassis/Slot/Port' not in section:
            continue
        
        # Extract port ID
        port_match = re.search(r'Chassis/Slot/Port\s*:\s*(\d+/\d+/\d+)', section)
        if not port_match:
            continue
        
        port_id = port_match.group(1)
        
        # Parse this port's data using existing detailed parser
        port_data = parse_show_interfaces_detailed(section, port_id)
        ports_data[port_id] = port_data
    
    return ports_data


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


def parse_show_interfaces_port(output: str, port_id: str) -> Dict[str, str]:
    """
    Parse 'show interfaces port X' output (detailed single port view).
    
    Format:
    Chassis/Slot/Port          : 1/1/19  
     Operational Status        : up,
     Admin Status              : enabled,
     BandWidth (Megabits)      :     1000,  		Duplex           : Full,
    
    Returns dict with port details.
    """
    result = {
        "port_id": port_id,
        "admin_state": "unknown",
        "oper_state": "unknown",
        "speed": None,
        "duplex": None,
        "auto_neg": True
    }
    
    # Parse oper state
    oper_match = re.search(r'Operational Status\s*:\s*(\w+)', output, re.IGNORECASE)
    if oper_match:
        result["oper_state"] = oper_match.group(1).lower()
    
    # Parse admin state
    admin_match = re.search(r'Admin Status\s*:\s*(\w+)', output, re.IGNORECASE)
    if admin_match:
        admin = admin_match.group(1).lower()
        result["admin_state"] = "enabled" if admin in ["enabled", "enable"] else "disabled"
    
    # Parse speed (BandWidth)
    speed_match = re.search(r'BandWidth \(Megabits\)\s*:\s*(\d+)', output)
    if speed_match:
        speed_val = speed_match.group(1).strip()
        result["speed"] = f"{speed_val}Mbps"
    
    # Parse duplex
    duplex_match = re.search(r'Duplex\s*:\s*(\w+)', output, re.IGNORECASE)
    if duplex_match:
        result["duplex"] = duplex_match.group(1)
    
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
                "admin_state": "enabled" if admin == "en" else "disabled",
                "auto_neg": auto_neg == "en",
                "speed": None if speed == '-' else f"{speed}Mbps" if speed.isdigit() else speed,
                "duplex": None if duplex == '-' else duplex,
                "oper_state": oper_state
            }
    
    return interfaces


def parse_vlan_members(output: str) -> Dict[str, List[Tuple[int, str, str]]]:
    """
    Parse 'show vlan members' output.
    
    Returns dict keyed by port_id with list of (vlan_id, type, status) tuples.
    """
    port_vlans = {}
    
    lines = output.strip().split('\n')
    
    for line in lines:
        # Skip header
        if 'vlan' in line.lower() or '----' in line:
            continue
        
        # Parse: vlan port type status
        # Example: 19        1/1/4        tagged     forwarding
        match = re.match(r'\s*(\d+)\s+(\d+/\d+/\d+)\s+(\S+)\s+(\S+)', line)
        if match:
            vlan_id = int(match.group(1))
            port_id = match.group(2)
            vlan_type = match.group(3)  # tagged/untagged
            status = match.group(4)     # forwarding/inactive
            
            if port_id not in port_vlans:
                port_vlans[port_id] = []
            
            port_vlans[port_id].append((vlan_id, vlan_type, status))
    
    return port_vlans


def parse_vlan_members_port(output: str, port_id: str) -> List[Tuple[int, str, str]]:
    """
    Parse 'show vlan members port X' output (single port).
    
    Format:
      vlan      type        status
    --------+-----------+---------------
        51    untagged    forwarding
       101    tagged      forwarding
    
    Returns list of (vlan_id, type, status) tuples for the port.
    """
    vlans = []
    
    lines = output.strip().split('\n')
    
    for line in lines:
        # Skip header
        if 'vlan' in line.lower() or '----' in line:
            continue
        
        # Parse: vlan type status (NO port column)
        # Example: 51    untagged    forwarding
        match = re.match(r'\s*(\d+)\s+(\S+)\s+(\S+)', line)
        if match:
            vlan_id = int(match.group(1))
            vlan_type = match.group(2)  # tagged/untagged
            status = match.group(3)     # forwarding/inactive
            
            vlans.append((vlan_id, vlan_type, status))
    
    return vlans


def parse_mac_learning(output: str) -> Dict[str, List[Tuple[str, int]]]:
    """
    Parse 'show mac-learning' output.
    
    Returns dict keyed by port_id with list of (mac_address, vlan_id) tuples.
    """
    port_macs = {}
    
    lines = output.strip().split('\n')
    
    for line in lines:
        # Skip headers and legend
        if 'Legend:' in line or 'Domain' in line or '----' in line or 'Total number' in line:
            continue
        
        # Parse: Domain Vlan Mac Type Operation Interface
        # Example: VLAN   19   24:9a:d8:1f:20:99   dynamic   bridging   1/1/4
        match = re.search(r'VLAN\s+(\d+)\s+([0-9a-f:]+)\s+\S+\s+\S+\s+(\d+/\d+/\d+)', line, re.IGNORECASE)
        if match:
            vlan_id = int(match.group(1))
            mac = match.group(2)
            port_id = match.group(3)
            
            if port_id not in port_macs:
                port_macs[port_id] = []
            
            port_macs[port_id].append((mac, vlan_id))
    
    return port_macs


def parse_lldp_remote(output: str) -> Dict[str, Dict[str, str]]:
    """
    Parse 'show lldp remote-system' output.
    
    Returns dict keyed by port_id with neighbor information.
    """
    neighbors = {}
    current_port = None
    current_neighbor = {}
    
    lines = output.strip().split('\n')
    
    for line in lines:
        # Detect port section
        # Example: Remote LLDP nearest-bridge Agents on Local Port 1/1/4:
        port_match = re.search(r'Local Port (\d+/\d+/\d+)', line)
        if port_match:
            # Save previous neighbor if exists
            if current_port and current_neighbor:
                neighbors[current_port] = current_neighbor.copy()
            
            current_port = port_match.group(1)
            current_neighbor = {}
            continue
        
        # Parse chassis line
        # Example: Chassis 10.9.19.20, Port 24:9a:d8:1f:20:99:
        chassis_match = re.match(r'\s*Chassis\s+(\S+),\s+Port\s+(\S+):', line)
        if chassis_match:
            current_neighbor['chassis_id'] = chassis_match.group(1)
            current_neighbor['port_id'] = chassis_match.group(2).rstrip(':')
            continue
        
        # Parse key-value pairs
        # Example: System Name = SIP-T46U,
        kv_match = re.match(r'\s*(\w[\w\s]+?)\s*=\s*(.+?),?\s*$', line)
        if kv_match and current_port:
            key = kv_match.group(1).strip()
            value = kv_match.group(2).strip().rstrip(',')
            
            # Map to standard keys
            if key == "System Name":
                current_neighbor['system_name'] = value
            elif key == "System Description":
                current_neighbor['system_description'] = value
            elif key == "Port Description":
                current_neighbor['port_description'] = value
            elif key == "Management IP Address":
                current_neighbor['management_ip'] = value
            elif key == "Capabilities Enabled":
                current_neighbor['capabilities'] = value
    
    # Save last neighbor
    if current_port and current_neighbor:
        neighbors[current_port] = current_neighbor
    
    return neighbors


def aggregate_interface_data(
    status_data: Dict[str, Dict[str, str]],
    vlan_data: Dict[str, List[Tuple[int, str, str]]],
    mac_data: Dict[str, List[Tuple[str, int]]],
    lldp_data: Dict[str, Dict[str, str]],
    poe_data: Optional[Dict[str, Dict[str, any]]] = None,
    detailed_data: Optional[Dict[str, Dict[str, any]]] = None
) -> List[Dict[str, any]]:
    """
    Aggregate all interface data into unified structure.
    
    Returns list of dictionaries with complete port information.
    """
    interfaces = []
    
    for port_id, status in status_data.items():
        port_info = {
            "port_id": port_id,
            "admin_state": status.get("admin_state", "unknown"),
            "oper_state": status.get("oper_state", "down"),
            "speed": status.get("speed"),
            "duplex": status.get("duplex"),
            "auto_neg": status.get("auto_neg", True),
            "interface_type": None,
            "sfp_type": None,
            "mac_address": None,
            "vlan": {"untagged": None, "tagged": [], "status": None},
            "mac_addresses": [],
            "lldp_neighbor": None,
            "poe": None,
            "statistics": None,
            "description": None
        }
        
        # Add detailed info (SFP, interface type, MAC, statistics) if available
        if detailed_data and port_id in detailed_data:
            detail = detailed_data[port_id]
            port_info["interface_type"] = detail.get("interface_type")
            port_info["sfp_type"] = detail.get("sfp_type")
            port_info["mac_address"] = detail.get("mac_address")
            if detail.get("statistics"):
                port_info["statistics"] = detail["statistics"]
        
        # Add VLAN information
        if port_id in vlan_data:
            for vlan_id, vlan_type, vlan_status in vlan_data[port_id]:
                if vlan_type == "untagged":
                    port_info["vlan"]["untagged"] = vlan_id
                    port_info["vlan"]["status"] = vlan_status
                elif vlan_type == "tagged":
                    port_info["vlan"]["tagged"].append(vlan_id)
        
        # Add MAC addresses
        if port_id in mac_data:
            for mac, vlan in mac_data[port_id]:
                port_info["mac_addresses"].append({
                    "mac": mac,
                    "vlan": vlan,
                    "type": "dynamic"
                })
        
        # Add LLDP neighbor
        if port_id in lldp_data:
            neighbor = lldp_data[port_id]
            port_info["lldp_neighbor"] = {
                "chassis_id": neighbor.get("chassis_id"),
                "port_id": neighbor.get("port_id"),
                "port_description": neighbor.get("port_description"),
                "system_name": neighbor.get("system_name"),
                "system_description": neighbor.get("system_description"),
                "management_ip": neighbor.get("management_ip"),
                "capabilities": neighbor.get("capabilities")
            }
        
        # Add PoE information if available
        if poe_data and port_id in poe_data:
            poe = poe_data[port_id]
            port_info["poe"] = {
                "enabled": poe.get("admin_state") == "ON",
                "status": poe.get("status"),
                "power_used_mw": poe.get("actual_used_mw", 0),
                "max_power_mw": poe.get("max_power_mw", 0),
                "device_class": poe.get("class_"),
                "priority": poe.get("priority")
            }
        
        interfaces.append(port_info)
    
    return interfaces
