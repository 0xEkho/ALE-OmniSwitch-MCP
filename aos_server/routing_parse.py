"""AOS routing information parsers."""

from __future__ import annotations
import re
from typing import Dict, List, Any


def parse_show_vrf(output: str) -> List[Dict[str, Any]]:
    """Parse 'show vrf' output."""
    vrfs = []
    lines = output.strip().split('\n')
    
    for line in lines:
        line = line.strip()
        if not line or 'Virtual Routers' in line or '---' in line or 'Total Number' in line:
            continue
            
        # Match: default              default OSPF PIM VRRP
        match = re.match(r'^(\S+)\s+(\S+)\s+(.+)$', line)
        if match:
            vrf_name = match.group(1)
            profile = match.group(2)
            protocols = match.group(3).strip().split()
            
            vrfs.append({
                'name': vrf_name,
                'profile': profile,
                'protocols': protocols
            })
    
    return vrfs


def parse_show_ip_routes(output: str, limit: int = None, protocol_filter: str = None) -> Dict[str, Any]:
    """Parse 'show ip routes' output."""
    routes = []
    total_routes = 0
    lines = output.strip().split('\n')
    
    # Extract total
    for line in lines:
        if 'Total' in line and 'routes' in line:
            match = re.search(r'Total\s+(\d+)\s+routes', line)
            if match:
                total_routes = int(match.group(1))
                break
    
    count = 0
    for line in lines:
        line = line.strip()
        if not line or 'Dest Address' in line or '---' in line or '+' in line or 'Total' in line:
            continue
        
        # Match route line: 0.0.0.0/0            10.255.9.1          36d 3h   OSPF
        parts = line.split()
        if len(parts) >= 3:
            destination = parts[0]
            gateway = parts[1]
            if len(parts) == 3:
                age = None
                protocol = parts[2]
            elif len(parts) == 4:
                age = parts[2]
                protocol = parts[3]
            else:
                age = ' '.join(parts[2:-1])
                protocol = parts[-1]
            
            if protocol_filter and protocol.upper() != protocol_filter.upper():
                continue
                
            routes.append({
                'destination': destination,
                'gateway': gateway,
                'age': age,
                'protocol': protocol
            })
            count += 1
            if limit and count >= limit:
                break
    
    return {
        'total_routes': total_routes,
        'routes': routes,
        'truncated': limit and total_routes > limit
    }


def parse_show_ip_ospf_interface(output: str) -> List[Dict[str, Any]]:
    """Parse 'show ip ospf interface' output."""
    interfaces = []
    lines = output.strip().split('\n')
    
    for line in lines:
        line = line.strip()
        if not line or 'Interface' in line or '---' in line:
            continue
        
        parts = line.split()
        if len(parts) >= 8:
            interfaces.append({
                'interface': parts[0],
                'domain_name': parts[1] if len(parts) > 1 else None,
                'domain_id': parts[2] if len(parts) > 2 else None,
                'dr_address': parts[3] if len(parts) > 3 else None,
                'backup_dr': parts[4] if len(parts) > 4 else None,
                'admin_status': parts[5] if len(parts) > 5 else None,
                'oper_status': parts[6] if len(parts) > 6 else None,
                'state': parts[7] if len(parts) > 7 else None,
                'bfd_status': parts[8] if len(parts) > 8 else None
            })
    
    return interfaces


def parse_show_ip_ospf_neighbor(output: str) -> List[Dict[str, Any]]:
    """Parse 'show ip ospf neighbor' output."""
    neighbors = []
    lines = output.strip().split('\n')
    
    for line in lines:
        line = line.strip()
        if not line or '---' in line or 'Total' in line:
            continue
        if 'IP' in line and 'Address' in line and 'Area' in line:
            continue
            
        parts = line.split()
        if len(parts) >= 6:
            neighbors.append({
                'router_id': parts[0],
                'address': parts[1],
                'area_id': parts[2],
                'device_type': parts[3],
                'interface_id': parts[4],
                'state': parts[5]
            })
    
    return neighbors


def parse_show_ip_interface(output: str) -> List[Dict[str, Any]]:
    """Parse 'show ip interface' output."""
    interfaces = []
    lines = output.strip().split('\n')
    
    for line in lines:
        line = line.strip()
        if not line or 'IP Address' in line or '---' in line:
            continue
        
        parts = line.split()
        if len(parts) >= 3:
            interfaces.append({
                'interface': parts[0],
                'ip_address': parts[1] if len(parts) > 1 else None,
                'admin_status': parts[2] if len(parts) > 2 else None,
                'oper_status': parts[3] if len(parts) > 3 else None,
                'state': parts[4] if len(parts) > 4 else None
            })
    
    return interfaces
