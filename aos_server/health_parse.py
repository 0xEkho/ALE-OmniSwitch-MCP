"""
Health and chassis monitoring parsers for OmniSwitch AOS.

Parses output from:
- show health
- show health all
- show chassis
- show temperature
- show fan
- show power-supply
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional


def parse_show_health(output: str) -> Dict[str, Any]:
    """
    Parse 'show health' command output.
    
    Supports multiple AOS formats:
    - AOS8 chassis format (Module Slot Status CPU Memory RX TX)
    - OS6860 compact format (CMM Resources table)
    
    Returns structured health information including CPU, memory, and error thresholds.
    """
    result = {
        "modules": [],
        "overall_status": "OK",
        "issues": []
    }
    
    lines = output.strip().split('\n')
    
    # Detect OS6860 format: CMM Resources table
    if "Resources" in output and "Current" in output:
        cpu_usage = 0
        memory_usage = 0
        
        for line in lines:
            # CPU line: "CPU                     38       40      32      31"
            cpu_match = re.search(r'^CPU\s+(\d+)', line)
            if cpu_match:
                cpu_usage = int(cpu_match.group(1))
            
            # Memory line: "Memory                  10       10      10      10"
            memory_match = re.search(r'^Memory\s+(\d+)', line)
            if memory_match:
                memory_usage = int(memory_match.group(1))
        
        # Add single CMM module
        if cpu_usage > 0 or memory_usage > 0:
            module = {
                "module_name": "CMM",
                "slot": "1",
                "status": "OK",
                "cpu_usage_percent": cpu_usage,
                "memory_usage_percent": memory_usage,
                "rx_errors": 0,
                "tx_errors": 0
            }
            result["modules"].append(module)
            
            # Check thresholds
            if cpu_usage > 80:
                result["overall_status"] = "WARNING"
                result["issues"].append(f"CMM CPU usage high: {cpu_usage}%")
            if memory_usage > 85:
                result["overall_status"] = "WARNING"
                result["issues"].append(f"CMM memory usage high: {memory_usage}%")
    
    else:
        # AOS8 chassis format: Module   Slot   Status   CPU%   Memory%   RX Errors   TX Errors
        for line in lines:
            match = re.search(r'(\w+)\s+(\d+/?\d*)\s+(OK|WARNING|CRITICAL|DOWN)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)', line)
            if match:
                module_name, slot, status, cpu, memory, rx_errors, tx_errors = match.groups()
                
                module = {
                    "module_name": module_name,
                    "slot": slot,
                    "status": status,
                    "cpu_usage_percent": int(cpu),
                    "memory_usage_percent": int(memory),
                    "rx_errors": int(rx_errors),
                    "tx_errors": int(tx_errors)
                }
                
                result["modules"].append(module)
                
                # Update overall status
                if status in ["WARNING", "CRITICAL", "DOWN"]:
                    result["overall_status"] = status
                    result["issues"].append(f"{module_name} slot {slot} status: {status}")
                
                # Check thresholds
                if int(cpu) > 80:
                    result["issues"].append(f"{module_name} slot {slot} CPU usage high: {cpu}%")
                if int(memory) > 85:
                    result["issues"].append(f"{module_name} slot {slot} memory usage high: {memory}%")
    
    return result


def parse_show_chassis(output: str) -> Dict[str, Any]:
    """
    Parse 'show chassis' command output.
    
    Returns chassis information including model, serial, slots, and hardware details.
    """
    result = {
        "chassis_type": None,
        "serial_number": None,
        "hardware_revision": None,
        "mac_address": None,
        "slots": [],
        "modules": []
    }
    
    lines = output.strip().split('\n')
    
    for line in lines:
        # Chassis type
        if 'Chassis Type' in line or 'Model Name' in line:
            match = re.search(r':\s*(.+?)(?:,|$)', line)
            if match:
                result["chassis_type"] = match.group(1).strip()
        
        # Serial number
        if 'Serial Number' in line:
            match = re.search(r':\s*(\S+)', line)
            if match:
                result["serial_number"] = match.group(1).strip().rstrip(',')
        
        # Hardware revision
        if 'Hardware Revision' in line:
            match = re.search(r':\s*(\S+)', line)
            if match:
                result["hardware_revision"] = match.group(1).strip().rstrip(',')
        
        # MAC address
        if 'MAC Address' in line or 'Base MAC' in line:
            match = re.search(r':\s*([0-9a-fA-F:]+)', line)
            if match:
                result["mac_address"] = match.group(1).strip()
    
    return result


def parse_show_temperature(output: str) -> Dict[str, Any]:
    """
    Parse 'show temperature' command output.
    
    Supports multiple formats:
    - AOS8: Sensor Location Current Threshold Status
    - OS6860: Chassis/Device | Current | Range | Danger | Thresh | Status
    
    Returns temperature readings for chassis components.
    """
    result = {
        "sensors": [],
        "overall_status": "OK",
        "issues": []
    }
    
    lines = output.strip().split('\n')
    
    for line in lines:
        # OS6860 format: "1/CMMA            38       15 to 85      88       85     UNDER THRESHOLD"
        os6860_match = re.search(r'(\d+/\w+)\s+(\d+)\s+\d+\s+to\s+\d+\s+\d+\s+(\d+)\s+(UNDER THRESHOLD|OVER THRESHOLD|OK)', line, re.IGNORECASE)
        if os6860_match:
            location, current, threshold, status = os6860_match.groups()
            
            sensor = {
                "sensor": location,
                "location": location,
                "current_celsius": int(current),
                "threshold_celsius": int(threshold),
                "status": "OK" if "UNDER" in status.upper() else "CRITICAL"
            }
            
            result["sensors"].append(sensor)
            
            if "OVER" in status.upper() or int(current) >= int(threshold):
                result["overall_status"] = "CRITICAL"
                result["issues"].append(f"{location}: {current}°C (threshold: {threshold}°C)")
            continue
        
        # AOS8 format: "Sensor   Location   Current   Threshold   Status"
        aos8_match = re.search(r'(\w+[-\w]*)\s+([\w/]+)\s+(\d+)C?\s+(\d+)C?\s+(OK|WARNING|CRITICAL)', line, re.IGNORECASE)
        if aos8_match:
            sensor_name, location, current, threshold, status = aos8_match.groups()
            
            sensor = {
                "sensor": sensor_name,
                "location": location,
                "current_celsius": int(current),
                "threshold_celsius": int(threshold),
                "status": status.upper()
            }
            
            result["sensors"].append(sensor)
            
            if status.upper() in ["WARNING", "CRITICAL"]:
                result["overall_status"] = status.upper()
                result["issues"].append(f"{sensor_name} at {location}: {current}°C (threshold: {threshold}°C)")
    
    return result


def parse_show_fan(output: str) -> List[Dict[str, Any]]:
    """
    Parse 'show fan' or 'show fantray' command output.
    
    Supports multiple formats:
    - AOS8: Fan ID   Speed (RPM)   Status
    - OS6860: Chassis/Tray | Fan | Functional
    
    Returns fan status information.
    """
    fans = []
    
    lines = output.strip().split('\n')
    
    for line in lines:
        # OS6860 format: "1/--         1       YES"
        os6860_match = re.search(r'(\d+)/[-\w]*\s+(\d+)\s+(YES|NO)', line, re.IGNORECASE)
        if os6860_match:
            chassis, fan_id, functional = os6860_match.groups()
            
            fan = {
                "fan_id": int(fan_id),
                "speed_rpm": 3500 if functional.upper() == "YES" else 0,  # Default speed if functional
                "status": "OK" if functional.upper() == "YES" else "FAILED"
            }
            
            fans.append(fan)
            continue
        
        # AOS8 format: "Fan ID   Speed (RPM)   Status"
        aos8_match = re.search(r'(?:Fan|FAN)\s+(\d+)\s+(\d+)\s*(RPM)?\s+(OK|WARNING|CRITICAL|FAILED|operational|not operational)', line, re.IGNORECASE)
        if aos8_match:
            fan_id, speed, _, status = aos8_match.groups()
            
            fan = {
                "fan_id": int(fan_id),
                "speed_rpm": int(speed),
                "status": status.upper() if status.upper() in ["OK", "WARNING", "CRITICAL", "FAILED"] else ("OK" if "operational" in status.lower() else "FAILED")
            }
            
            fans.append(fan)
    
    return fans


def parse_show_power_supply(output: str) -> List[Dict[str, Any]]:
    """
    Parse 'show power-supply' command output.
    
    Returns power supply status information.
    """
    power_supplies = []
    
    lines = output.strip().split('\n')
    
    for line in lines:
        # PSU format: PSU   Status   Type   Watts
        match = re.search(r'(?:PSU|PS|Power Supply)\s+(\d+)\s+(present|not present|operational|failed)\s+(AC|DC)?\s*(\d+)?', line, re.IGNORECASE)
        if match:
            psu_id, status, psu_type, watts = match.groups()
            
            psu = {
                "psu_id": int(psu_id),
                "status": "present" if "present" in status.lower() and "not" not in status.lower() else "not_present",
                "operational": "operational" in status.lower(),
                "type": psu_type if psu_type else "unknown",
                "watts": int(watts) if watts else None
            }
            
            power_supplies.append(psu)
    
    return power_supplies


def parse_show_cmm(output: str) -> Dict[str, Any]:
    """
    Parse 'show cmm' command output.
    
    Returns Chassis Management Module information.
    """
    result = {
        "primary": None,
        "secondary": None,
        "status": "unknown"
    }
    
    lines = output.strip().split('\n')
    
    for line in lines:
        # CMM format: Slot   Role   Status   Temperature
        match = re.search(r'(?:Slot|CMM)\s+(\d+)\s+(primary|secondary|running|standby)\s+(running|standby|up|down)\s*(\d+)?', line, re.IGNORECASE)
        if match:
            slot, role, status, temp = match.groups()
            
            cmm_info = {
                "slot": int(slot),
                "role": role.lower(),
                "status": status.lower(),
                "temperature_celsius": int(temp) if temp else None
            }
            
            if "primary" in role.lower() or "running" in role.lower():
                result["primary"] = cmm_info
                result["status"] = status.lower()
            elif "secondary" in role.lower() or "standby" in role.lower():
                result["secondary"] = cmm_info
    
    return result


def analyze_chassis_health(chassis_data: Dict[str, Any], temp_data: Dict[str, Any], 
                          fan_data: List[Dict[str, Any]], psu_data: List[Dict[str, Any]]) -> List[str]:
    """
    Analyze combined chassis data and generate issues list.
    
    Returns list of detected issues.
    """
    issues = []
    
    # Temperature issues
    for sensor in temp_data.get("sensors", []):
        if sensor["status"] != "OK":
            issues.append(f"Temperature sensor {sensor['sensor']} at {sensor['location']}: "
                         f"{sensor['current_celsius']}°C (threshold: {sensor['threshold_celsius']}°C)")
    
    # Fan issues
    for fan in fan_data:
        if fan["status"] != "OK":
            issues.append(f"Fan {fan['fan_id']} status: {fan['status']}")
        if fan["speed_rpm"] < 1000:
            issues.append(f"Fan {fan['fan_id']} speed low: {fan['speed_rpm']} RPM")
    
    # PSU issues
    for psu in psu_data:
        if psu["status"] != "present":
            issues.append(f"Power supply {psu['psu_id']}: {psu['status']}")
        if not psu["operational"]:
            issues.append(f"Power supply {psu['psu_id']} not operational")
    
    return issues
