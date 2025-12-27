"""
VLAN parsing utilities for AOS OmniSwitch.
"""

import re
from typing import Dict, List, Optional, Tuple


def parse_show_vlan(output: str) -> List[Dict[str, any]]:
    """
    Parse 'show vlan' output to extract basic VLAN information.
    
    Example output:
     vlan    type   admin   oper    ip    mtu          name
    ------+-------+-------+------+------+------+------------------
    1      std       Ena     Dis   Dis    1500    NE PAS UTILISER
    2      std       Ena     Dis   Ena    1500    GTB
    
    Returns list of dicts with VLAN info.
    """
    vlans = []
    lines = output.strip().split('\n')
    
    for line in lines:
        # Skip headers and separators
        if 'vlan' in line.lower() and 'type' in line.lower():
            continue
        if '----' in line or not line.strip():
            continue
        
        # Parse: vlan type admin oper ip mtu name
        # Example: 1      std       Ena     Dis   Dis    1500    NE PAS UTILISER
        match = re.match(
            r'\s*(\d+)\s+(\w+)\s+(Ena|Dis)\s+(Ena|Dis)\s+(Ena|Dis)\s+(\d+)\s+(.*)$',
            line
        )
        
        if match:
            vlan_id = int(match.group(1))
            vlan_type = match.group(2)
            admin = match.group(3)
            oper = match.group(4)
            ip_routing = match.group(5)
            mtu = int(match.group(6))
            name = match.group(7).strip()
            
            vlans.append({
                'vlan_id': vlan_id,
                'name': name,
                'type': vlan_type,
                'admin_state': admin,
                'oper_state': oper,
                'ip_routing': ip_routing,
                'mtu': mtu
            })
    
    return vlans


def parse_show_vlan_detail(output: str) -> Dict[str, any]:
    """
    Parse 'show vlan <id>' output for detailed VLAN information.
    
    Example output:
    Name                     : GTB,
    Type                     : Static Vlan,
    Administrative State     : enabled,
    Operational State        : disabled,
    IP Routing               : enabled,
    IP MTU                   : 1500
    MAC Tunneling            : disabled,
    
    Returns dict with detailed VLAN configuration.
    """
    vlan_detail = {}
    
    lines = output.strip().split('\n')
    
    for line in lines:
        # Parse key-value pairs
        if ':' in line:
            parts = line.split(':', 1)
            if len(parts) == 2:
                key = parts[0].strip()
                value = parts[1].strip().rstrip(',')
                
                # Map keys to standard field names
                if key == "Name":
                    vlan_detail['name'] = value
                elif key == "Type":
                    vlan_detail['type'] = value
                elif key == "Administrative State":
                    vlan_detail['admin_state'] = value
                elif key == "Operational State":
                    vlan_detail['oper_state'] = value
                elif key == "IP Routing":
                    vlan_detail['ip_routing'] = value
                elif key == "IP MTU":
                    vlan_detail['mtu'] = int(value) if value.isdigit() else None
                elif key == "MAC Tunneling":
                    vlan_detail['mac_tunneling'] = value
    
    return vlan_detail


def analyze_vlan_config(vlans: List[Dict[str, any]]) -> Tuple[Dict[str, int], List[str]]:
    """
    Analyze VLAN configuration and detect potential issues.
    
    Returns:
        - summary: Dict with statistics
        - issues: List of detected configuration issues
    """
    summary = {
        'total': len(vlans),
        'enabled': 0,
        'disabled': 0,
        'operational': 0,
        'down': 0,
        'with_ip_routing': 0,
        'std_vlans': 0,
        'vcm_vlans': 0,
    }
    
    issues = []
    
    for vlan in vlans:
        vlan_id = vlan['vlan_id']
        name = vlan['name']
        admin = vlan['admin_state']
        oper = vlan['oper_state']
        ip_routing = vlan.get('ip_routing', 'Dis')
        vlan_type = vlan['type']
        
        # Count states
        if admin == 'Ena':
            summary['enabled'] += 1
        else:
            summary['disabled'] += 1
        
        if oper == 'Ena':
            summary['operational'] += 1
        else:
            summary['down'] += 1
        
        if ip_routing == 'Ena':
            summary['with_ip_routing'] += 1
        
        if vlan_type == 'std':
            summary['std_vlans'] += 1
        elif vlan_type == 'vcm':
            summary['vcm_vlans'] += 1
        
        # Detect issues
        if admin == 'Ena' and oper == 'Dis':
            issues.append(f"VLAN {vlan_id} ({name}): Enabled but operationally down")
        
        if vlan_id == 1 and admin == 'Ena':
            issues.append(f"VLAN 1: Default VLAN is enabled - consider disabling if unused")
        
        # Check for suspicious names
        if any(keyword in name.lower() for keyword in ['test', 'temp', 'old', 'unused', 'ne pas', 'poubelle', 'toto']):
            issues.append(f"VLAN {vlan_id} ({name}): Suspicious name suggests temporary/test VLAN")
    
    return summary, issues
