"""
LACP and Link Aggregation parsers for OmniSwitch AOS.

Parses output from:
- show linkagg
- show linkagg agg <id>
- show lacp
- show lacp statistics
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional


def parse_show_linkagg(output: str) -> Dict[str, Any]:
    """
    Parse 'show linkagg' command output.
    
    Returns link aggregation groups with their configuration and status.
    """
    result = {
        "lags": [],
        "total_lags": 0,
        "issues": []
    }
    
    lines = output.strip().split('\n')
    
    for line in lines:
        # OS6860 format: Number  Aggregate     SNMP Id   Size Admin State  Oper State     Att/Sel Ports
        # Example:         5     Dynamic      40000005   2   ENABLED      UP              2   2
        os6860_match = re.search(
            r'^\s*(\d+)\s+(\S+)\s+\d+\s+(\d+)\s+(ENABLED|DISABLED)\s+(UP|DOWN)\s+(\d+)\s+(\d+)',
            line
        )
        if os6860_match:
            agg_num, name, size, admin, oper, attached, selected = os6860_match.groups()
            
            lag = {
                "agg_id": agg_num,
                "name": name if name != "---" else f"agg{agg_num}",
                "size": int(size),
                "admin_state": admin.lower(),
                "oper_state": oper.lower(),
                "type": "lacp" if "dynamic" in name.lower() else "static",
                "hash_algorithm": "unknown",
                "members": [],
                "attached_ports": int(attached),
                "selected_ports": int(selected)
            }
            
            result["lags"].append(lag)
            result["total_lags"] += 1
            
            # Detect issues
            if admin.lower() == "enabled" and oper.lower() == "down":
                result["issues"].append(
                    f"LAG {agg_num} ({name}): administratively enabled but operationally down"
                )
            if int(selected) < int(attached):
                result["issues"].append(
                    f"LAG {agg_num} ({name}): {int(attached) - int(selected)} port(s) attached but not selected"
                )
            continue
        
        # Original format: Agg   Name        Size  AdminState  OperState  Type      Hash
        # Example: 1    uplink-core  2     enabled     up         lacp      src-dst-mac
        match = re.search(
            r'(\d+)\s+(\S+)\s+(\d+)\s+(enabled|disabled)\s+(up|down)\s+(lacp|static)\s+(\S+)',
            line,
            re.IGNORECASE
        )
        if match:
            agg_id, name, size, admin, oper, lag_type, hash_alg = match.groups()
            
            lag = {
                "agg_id": agg_id,
                "name": name if name != "---" else f"agg{agg_id}",
                "size": int(size),
                "admin_state": admin.lower(),
                "oper_state": oper.lower(),
                "type": lag_type.lower(),
                "hash_algorithm": hash_alg,
                "members": []
            }
            
            result["lags"].append(lag)
            result["total_lags"] += 1
            
            # Detect issues
            if admin == "enabled" and oper.lower() == "down":
                result["issues"].append(
                    f"LAG {agg_id} ({name}): administratively enabled but operationally down"
                )
    
    return result


def parse_show_lacp(output: str) -> Dict[str, Any]:
    """
    Parse 'show lacp' command output.
    
    Returns LACP protocol status and statistics.
    """
    result = {
        "lacp_enabled": False,
        "aggregates": [],
        "system_id": None,
        "system_priority": None
    }
    
    lines = output.strip().split('\n')
    
    for line in lines:
        # System information
        if "System ID:" in line or "System MAC:" in line:
            match = re.search(r':\s*([0-9a-fA-F:]{17})', line)
            if match:
                result["system_id"] = match.group(1)
        
        if "System Priority:" in line:
            match = re.search(r':\s*(\d+)', line)
            if match:
                result["system_priority"] = int(match.group(1))
        
        # LACP enabled check
        if re.search(r'LACP\s+(Enabled|Active)', line, re.IGNORECASE):
            result["lacp_enabled"] = True
        
        # Aggregate with LACP
        # Format: Agg   Port     Partner System      Partner Port
        agg_match = re.search(
            r'(\d+)\s+(\d+/\d+/\d+)\s+([0-9a-fA-F:]{17})\s+(\S+)',
            line
        )
        if agg_match:
            agg_id, port, partner_sys, partner_port = agg_match.groups()
            
            # Find or create aggregate entry
            agg_entry = next((a for a in result["aggregates"] if a["agg_id"] == agg_id), None)
            if not agg_entry:
                agg_entry = {"agg_id": agg_id, "ports": []}
                result["aggregates"].append(agg_entry)
            
            agg_entry["ports"].append({
                "port": port,
                "partner_system": partner_sys,
                "partner_port": partner_port
            })
    
    return result


def analyze_lacp_issues(lacp_data: Dict[str, Any], linkagg_data: Dict[str, Any]) -> List[str]:
    """
    Analyze LACP and link aggregation data to detect issues.
    
    Returns list of detected issues.
    """
    issues = []
    
    # Check if LACP is required but not enabled
    lacp_lags = [lag for lag in linkagg_data.get("lags", []) if lag.get("type") == "lacp"]
    if lacp_lags and not lacp_data.get("lacp_enabled"):
        issues.append("LACP LAGs configured but LACP protocol not enabled")
    
    # Check for LAGs with no active members
    for lag in linkagg_data.get("lags", []):
        if lag.get("oper_state") == "down" and lag.get("admin_state") == "enabled":
            issues.append(f"LAG {lag['agg_id']} ({lag.get('name', 'unknown')}): no active members")
    
    # Check for member ports in standby
    for lag in linkagg_data.get("lags", []):
        standby_count = len([m for m in lag.get("members", []) if m.get("status") == "standby"])
        if standby_count > 0:
            issues.append(
                f"LAG {lag['agg_id']} ({lag.get('name', 'unknown')}): "
                f"{standby_count} member(s) in standby"
            )
    
    return issues
