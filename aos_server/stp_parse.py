"""Spanning Tree parsing functions for AOS switches."""
import re
from typing import Dict, List, Any


def parse_show_spantree_mode(output: str) -> Dict[str, Any]:
    """Parse 'show spantree mode' output."""
    result = {}
    
    for line in output.splitlines():
        line = line.strip()
        if ':' not in line:
            continue
        
        if 'Current Running Mode' in line:
            result['mode'] = line.split(':')[1].strip().rstrip(',')
        elif 'Current Protocol' in line:
            result['protocol'] = line.split(':')[1].strip().rstrip(',')
        elif 'Path Cost Mode' in line:
            result['path_cost_mode'] = line.split(':')[1].strip().rstrip(',')
        elif 'Auto Vlan Containment' in line:
            result['auto_vlan_containment'] = line.split(':')[1].strip()
    
    return result


def parse_show_spantree_cist(output: str) -> Dict[str, Any]:
    """Parse 'show spantree cist' output."""
    result = {}
    
    for line in output.splitlines():
        line = line.strip()
        if ':' not in line:
            continue
        
        parts = line.split(':', 1)
        if len(parts) != 2:
            continue
        
        key = parts[0].strip()
        value = parts[1].strip().rstrip(',')
        
        if 'Spanning Tree Status' in key:
            result['stp_status'] = value
        elif key == 'Protocol':
            result['protocol'] = value
        elif key == 'mode':
            result['mode'] = value
        elif key == 'Priority':
            result['priority'] = value
        elif key == 'Bridge ID':
            result['bridge_id'] = value
        elif key == 'CST Designated Root':
            result['cst_designated_root'] = value
        elif key == 'Cost to CST Root':
            try:
                result['cost_to_cst_root'] = int(value)
            except:
                result['cost_to_cst_root'] = value
        elif key == 'Designated Root':
            result['designated_root'] = value
        elif key == 'Cost to Root Bridge':
            try:
                result['cost_to_root'] = int(value)
            except:
                result['cost_to_root'] = value
        elif key == 'Root Port':
            result['root_port'] = value
        elif key == 'Topology Changes':
            try:
                result['topology_changes'] = int(value)
            except:
                result['topology_changes'] = value
        elif key == 'Topology age':
            result['topology_age'] = value
        elif key == 'Last TC Rcvd Port':
            result['last_tc_port'] = value
        elif key == 'Last TC Rcvd Bridge':
            result['last_tc_bridge'] = value
        elif 'Max Age' in key and '=' in line:
            result['max_age'] = value.split('=')[1].strip().rstrip(',')
        elif 'Forward Delay' in key and '=' in line:
            result['forward_delay'] = value.split('=')[1].strip().rstrip(',')
        elif 'Hello Time' in key and '=' in line:
            result['hello_time'] = value.split('=')[1].strip()
    
    return result


def parse_show_spantree_ports(output: str) -> List[Dict[str, Any]]:
    """Parse 'show spantree ports' output."""
    ports = []
    
    lines = output.splitlines()
    in_data = False
    
    for line in lines:
        line = line.strip()
        
        # Skip header lines
        if 'Msti' in line and 'Port' in line and 'Oper Status' in line:
            in_data = True
            continue
        
        if not in_data or not line or line.startswith('---'):
            continue
        
        # Parse data line
        parts = line.split()
        if len(parts) >= 6:
            msti = parts[0]
            port_id = parts[1]
            oper_status = parts[2]
            path_cost = parts[3]
            role = parts[4]
            loop_guard = parts[5]
            
            # Skip header duplicates
            if msti == 'Msti' or port_id == 'Port':
                continue
            
            ports.append({
                'msti': msti,
                'port_id': port_id,
                'oper_status': oper_status,
                'path_cost': path_cost,
                'role': role,
                'loop_guard': loop_guard
            })
    
    return ports


def parse_show_spantree_vlan(output: str) -> List[Dict[str, Any]]:
    """Parse 'show spantree vlan' output."""
    vlans = []
    
    lines = output.splitlines()
    in_data = False
    
    for line in lines:
        line = line.strip()
        
        # Look for data header
        if 'Vlan' in line and 'STP Status' in line and 'Protocol' in line:
            in_data = True
            continue
        
        if not in_data or not line or line.startswith('---'):
            continue
        
        # Skip informational lines
        if 'Spanning Tree' in line or 'Inactive' in line or 'Path Cost Mode' in line:
            continue
        
        # Parse data line
        parts = line.split()
        if len(parts) >= 4:
            vlan_id = parts[0]
            status = parts[1]
            protocol = parts[2]
            priority = parts[3]
            
            # Skip header duplicates
            if vlan_id == 'Vlan':
                continue
            
            try:
                vlans.append({
                    'vlan_id': int(vlan_id),
                    'status': status,
                    'protocol': protocol,
                    'priority': priority
                })
            except ValueError:
                # Skip lines that don't start with a number
                continue
    
    return vlans
