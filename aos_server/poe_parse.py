# poe_parse.py
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional, Dict, Any


@dataclass(frozen=True)
class PoEPort:
    port_id: str
    max_power_mw: int
    actual_used_mw: int
    status: str
    priority: str
    admin_state: str
    class_: Optional[str] = None
    type_: Optional[str] = None


def parse_show_lanpower(output: str) -> Dict[str, Any]:
    """
    Parse 'show lanpower slot X/Y' output into structured data.
    
    Returns a dict with:
    - ports: List[Dict] with port details
    - chassis_summary: Dict with chassis/slot aggregates
    """
    
    ports: List[Dict[str, Any]] = []
    chassis_summary: Dict[str, Any] = {}
    
    lines = output.splitlines()
    in_port_section = False
    
    for idx, line in enumerate(lines):
        line_stripped = line.strip()
        
        # Detect port section start (after header line with dashes)
        if "----" in line and idx > 0 and "Port" in lines[idx - 1]:
            in_port_section = True
            continue
        
        # Parse port lines (until we reach chassis info)
        if in_port_section and line_stripped and not line_stripped.startswith("Chassis"):
            # Flexible regex: port_id max_mw actual_mw status priority admin_state class type
            match = re.match(
                r'^(\d+/\d+/\d+)\s+(\d+)\s+(\d+)\s+(\S+(?:\s+\S+)*?)\s+(Low|High|Critical)\s+(ON|OFF)\s+(.?)\s*(.*?)$',
                line_stripped
            )
            if match:
                port_entry = {
                    "port_id": match.group(1),
                    "max_power_mw": int(match.group(2)),
                    "actual_used_mw": int(match.group(3)),
                    "status": match.group(4).strip(),
                    "priority": match.group(5),
                    "admin_state": match.group(6),
                    "class": match.group(7) if match.group(7) and match.group(7) != "_" else None,
                    "type": match.group(8).strip() if match.group(8).strip() else None,
                }
                ports.append(port_entry)
        
        # Parse chassis summary section
        if "ChassisId" in line_stripped:
            m = re.match(r'ChassisId\s+(\d+)\s+Slot\s+(\d+)\s+Max Watts\s+(\d+)', line_stripped)
            if m:
                chassis_summary["chassis_id"] = int(m.group(1))
                chassis_summary["slot_id"] = int(m.group(2))
                chassis_summary["max_watts"] = int(m.group(3))
        
        elif "Actual Power Consumed" in line_stripped:
            m = re.match(r'(\d+)\s+Watts\s+Actual Power Consumed', line_stripped)
            if m:
                chassis_summary["actual_power_consumed_watts"] = int(m.group(1))
        
        elif "Actual Power Budget Remaining" in line_stripped:
            m = re.match(r'(\d+)\s+Watts\s+Actual Power Budget Remaining', line_stripped)
            if m:
                chassis_summary["power_budget_remaining_watts"] = int(m.group(1))
        
        elif "Total Power Budget Available" in line_stripped:
            m = re.match(r'(\d+)\s+Watts\s+Total Power Budget Available', line_stripped)
            if m:
                chassis_summary["total_power_budget_watts"] = int(m.group(1))
        
        elif "Power Supply Available" in line_stripped:
            m = re.match(r'(\d+)\s+Power Supply Available', line_stripped)
            if m:
                chassis_summary["power_supplies_available"] = int(m.group(1))
    
    return {
        "ports": ports,
        "chassis_summary": chassis_summary,
    }