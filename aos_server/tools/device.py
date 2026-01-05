"""Device tools - Facts, port info, port/interfaces discovery.

Tools: aos.device.facts, aos.port.info, aos.port.discover, aos.interfaces.discover
"""

import re
import time
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from .base import create_device_from_host, DeviceFacts, InterfaceInfo
from ..policy import compile_policy, sanitize_command
from ..config import AppConfig
from ..ssh_runner import SSHRunner
from ..interface_parse import parse_interfaces_status


# =============================================================================
# MODELS
# =============================================================================

class ArgsDeviceFacts(BaseModel):
    host: str = Field(description="Target switch IP address")
    port: Optional[int] = Field(default=22)
    refresh: bool = Field(default=True)


class ArgsPortInfo(BaseModel):
    host: str = Field(description="Target switch IP address")
    port_id: str = Field(description="Port identifier (e.g., '1/1/1')")
    port: Optional[int] = Field(default=22)


class ArgsPortDiscover(BaseModel):
    host: str = Field(description="Target switch IP address")
    port_id: str = Field(description="Port identifier (e.g., '1/1/1')")
    port: Optional[int] = Field(default=22)


class ArgsInterfacesDiscover(BaseModel):
    host: str = Field(description="Target switch IP address")
    port: Optional[int] = Field(default=22)
    include_inactive: bool = Field(default=True)
    include_statistics: bool = Field(default=False)


# =============================================================================
# PARSING HELPERS
# =============================================================================

def parse_system_output(output: str) -> Dict[str, Any]:
    """Parse 'show system' output."""
    facts = {}
    
    patterns = {
        'system_name': r'^\s*Name\s*:\s*(.+?),?\s*$',
        'description': r'^\s*Description\s*:\s*(.+?),?\s*$',
        'uptime': r'^\s*Up Time\s*:\s*(.+?),?\s*$',
        'contact': r'^\s*Contact\s*:\s*(.+?),?\s*$',
        'location': r'^\s*Location\s*:\s*(.+?),?\s*$',
    }
    
    for key, pattern in patterns.items():
        match = re.search(pattern, output, re.MULTILINE | re.IGNORECASE)
        if match:
            facts[key] = match.group(1).strip().rstrip(',')
    
    # Extract model and version from description
    if 'description' in facts:
        desc = facts['description']
        model_match = re.search(r'(OS\d+[A-Z0-9-]+)', desc)
        if model_match:
            facts['model'] = model_match.group(1)
        version_match = re.search(r'([\d]+\.[\d]+\.[\d]+\.R[\d]+)', desc)
        if version_match:
            facts['software_version'] = version_match.group(1)
    
    return facts


def parse_chassis_output(output: str) -> Dict[str, Any]:
    """Parse 'show chassis' output."""
    facts = {}
    
    patterns = {
        'serial_number': r'^\s*Serial Number\s*:\s*(\S+)',
        'base_mac': r'^\s*MAC Address\s*:\s*([0-9a-fA-F:]+)',
        'part_number': r'^\s*Part Number\s*:\s*(.+?),?\s*$',
        'hardware_revision': r'^\s*Hardware Revision\s*:\s*(\S+)',
    }
    
    for key, pattern in patterns.items():
        match = re.search(pattern, output, re.MULTILINE | re.IGNORECASE)
        if match:
            facts[key] = match.group(1).strip().rstrip(',')
    
    return facts


# =============================================================================
# HANDLERS
# =============================================================================

def handle_device_facts(
    cfg: AppConfig,
    runner: SSHRunner,
    args: Dict[str, Any],
    zone_resolver: Any = None,
) -> Dict[str, Any]:
    """Get device facts (model, serial, version, etc.)."""
    parsed = ArgsDeviceFacts.model_validate(args)
    device = create_device_from_host(parsed.host, parsed.port or 22)
    compiled_policy = compile_policy(cfg.command_policy)
    
    start_time = time.time()
    commands = ["show system", "show chassis"]
    results = {}
    
    for cmd in commands:
        safe_cmd = sanitize_command(cmd, compiled_policy)
        res = runner.run(device, safe_cmd, zone_resolver=zone_resolver)
        results[cmd] = res.stdout
    
    # Parse outputs
    system_facts = parse_system_output(results.get("show system", ""))
    chassis_facts = parse_chassis_output(results.get("show chassis", ""))
    
    facts = DeviceFacts(
        system_name=system_facts.get('system_name'),
        system_description=system_facts.get('description'),
        model=system_facts.get('model'),
        software_version=system_facts.get('software_version'),
        uptime=system_facts.get('uptime'),
        contact=system_facts.get('contact'),
        location=system_facts.get('location'),
        serial_number=chassis_facts.get('serial_number'),
        base_mac=chassis_facts.get('base_mac'),
        hardware_revision=chassis_facts.get('hardware_revision'),
    )
    
    duration_ms = int((time.time() - start_time) * 1000)
    
    return {
        "host": device.host,
        "hostname": facts.system_name,
        "model": facts.model,
        "aos_version": facts.software_version,
        "serial_number": facts.serial_number,
        "uptime": facts.uptime,
        "mac_address": facts.base_mac,
        "facts": facts.model_dump(),
        "duration_ms": duration_ms,
        "content": [
            {
                "type": "text",
                "text": f"**Device Facts: {device.host}**\n\n"
                       f"Model: {facts.model or 'N/A'}\n"
                       f"Version: {facts.software_version or 'N/A'}\n"
                       f"Serial: {facts.serial_number or 'N/A'}\n"
                       f"Uptime: {facts.uptime or 'N/A'}"
            }
        ]
    }


def handle_port_info(
    cfg: AppConfig,
    runner: SSHRunner,
    args: Dict[str, Any],
    zone_resolver: Any = None,
) -> Dict[str, Any]:
    """Get basic port information."""
    parsed = ArgsPortInfo.model_validate(args)
    device = create_device_from_host(parsed.host, parsed.port or 22)
    compiled_policy = compile_policy(cfg.command_policy)
    
    start_time = time.time()
    cmd = f"show interfaces port {parsed.port_id}"
    safe_cmd = sanitize_command(cmd, compiled_policy)
    res = runner.run(device, safe_cmd, zone_resolver=zone_resolver)
    
    output = res.stdout
    
    # Parse basic info
    admin_state = None
    oper_state = None
    speed = None
    duplex = None
    
    admin_match = re.search(r'Admin State\s*[:\-]\s*(\S+)', output, re.IGNORECASE)
    if admin_match:
        admin_state = admin_match.group(1)
    
    oper_match = re.search(r'(?:Operational Status|Link State)\s*[:\-]\s*(\S+)', output, re.IGNORECASE)
    if oper_match:
        oper_state = oper_match.group(1)
    
    speed_match = re.search(r'Speed\s*[:\-]\s*(.+?)[\r\n]', output, re.IGNORECASE)
    if speed_match:
        speed = speed_match.group(1).strip()
    
    duration_ms = int((time.time() - start_time) * 1000)
    
    return {
        "host": device.host,
        "port_id": parsed.port_id,
        "admin_state": admin_state,
        "oper_state": oper_state,
        "speed": speed,
        "duplex": duplex,
        "duration_ms": duration_ms,
    }


def handle_port_discover(
    cfg: AppConfig,
    runner: SSHRunner,
    args: Dict[str, Any],
    zone_resolver: Any = None,
) -> Dict[str, Any]:
    """Comprehensive port discovery with LLDP, VLAN, MAC, PoE."""
    parsed = ArgsPortDiscover.model_validate(args)
    device = create_device_from_host(parsed.host, parsed.port or 22)
    compiled_policy = compile_policy(cfg.command_policy)
    
    start_time = time.time()
    commands_executed = []
    
    # Gather all port info
    commands = [
        f"show interfaces port {parsed.port_id}",
        f"show vlan port {parsed.port_id}",
        f"show mac-learning port {parsed.port_id}",
        f"show lldp remote-system port {parsed.port_id}",
        f"show lanpower port {parsed.port_id}",
    ]
    
    results = {}
    for cmd in commands:
        safe_cmd = sanitize_command(cmd, compiled_policy)
        try:
            res = runner.run(device, safe_cmd, zone_resolver=zone_resolver)
            results[cmd.split()[1] if len(cmd.split()) > 1 else cmd] = res.stdout
            commands_executed.append(cmd)
        except Exception:
            pass  # Some commands may fail on certain ports
    
    # Build interface info
    interface = InterfaceInfo(
        port_id=parsed.port_id,
        admin_state="unknown",
        oper_state="unknown",
    )
    
    # Parse interface status
    intf_output = results.get("interfaces", "")
    if intf_output:
        admin_match = re.search(r'Admin State\s*[:\-]\s*(\S+)', intf_output, re.IGNORECASE)
        if admin_match:
            interface.admin_state = admin_match.group(1)
        oper_match = re.search(r'(?:Operational Status|Link State)\s*[:\-]\s*(\S+)', intf_output, re.IGNORECASE)
        if oper_match:
            interface.oper_state = oper_match.group(1)
    
    duration_ms = int((time.time() - start_time) * 1000)
    
    return {
        "host": device.host,
        "port_id": parsed.port_id,
        "interface": interface.model_dump(),
        "duration_ms": duration_ms,
        "commands_executed": commands_executed,
        "content": [
            {
                "type": "text",
                "text": f"**Port Discovery: {parsed.port_id}**\n\n"
                       f"Admin: {interface.admin_state}\n"
                       f"Oper: {interface.oper_state}"
            }
        ]
    }


def handle_interfaces_discover(
    cfg: AppConfig,
    runner: SSHRunner,
    args: Dict[str, Any],
    zone_resolver: Any = None,
) -> Dict[str, Any]:
    """Discover all interfaces on the switch."""
    parsed = ArgsInterfacesDiscover.model_validate(args)
    device = create_device_from_host(parsed.host, parsed.port or 22)
    compiled_policy = compile_policy(cfg.command_policy)
    
    start_time = time.time()
    
    cmd = "show interfaces status"
    safe_cmd = sanitize_command(cmd, compiled_policy)
    res = runner.run(device, safe_cmd, zone_resolver=zone_resolver)
    
    # Parse interfaces
    interfaces_dict = parse_interfaces_status(res.stdout)
    interfaces = list(interfaces_dict.values())
    
    # Filter if needed
    if not parsed.include_inactive:
        interfaces = [i for i in interfaces if i.get('oper_state', '').lower() == 'up']
    
    duration_ms = int((time.time() - start_time) * 1000)
    
    return {
        "host": device.host,
        "interfaces": interfaces,
        "total_count": len(interfaces),
        "duration_ms": duration_ms,
        "content": [
            {
                "type": "text",
                "text": f"**Interfaces Discovery: {device.host}**\n\n"
                       f"Total interfaces: {len(interfaces)}"
            }
        ]
    }


# =============================================================================
# TOOL INFO
# =============================================================================

TOOLS_INFO = [
    {
        "name": "aos.device.facts",
        "description": "Get essential device information for an OmniSwitch. "
                       "Use FIRST when: identifying a switch, checking firmware version, getting serial for support cases. "
                       "Returns: hostname, model (OS6860/OS6900/etc), serial_number, software_version, uptime_seconds, system_contact. "
                       "Combine with: aos.health.monitor for resource usage, aos.chassis.status for hardware health.",
        "input_schema": {
            "type": "object",
            "properties": {
                "host": {"type": "string", "description": "Switch IP address"},
            },
            "required": ["host"]
        },
        "output_schema": {"type": "object"}
    },
    {
        "name": "aos.port.info",
        "description": "Get basic status for a SINGLE port. "
                       "Use when: checking if port is up/down, verifying speed/duplex settings. "
                       "Returns: admin_state, oper_state, speed, duplex, link_status. "
                       "For detailed info: use aos.port.discover instead. For all ports: use aos.interfaces.discover.",
        "input_schema": {
            "type": "object",
            "properties": {
                "host": {"type": "string", "description": "Switch IP address"},
                "port_id": {"type": "string", "description": "Port identifier (e.g., '1/1/1')"},
            },
            "required": ["host", "port_id"]
        },
        "output_schema": {"type": "object"}
    },
    {
        "name": "aos.port.discover",
        "description": "COMPREHENSIVE discovery of what's connected to a specific port. "
                       "Use when: finding what device is on a port, troubleshooting connectivity, getting full port picture. "
                       "Returns: port status + LLDP neighbor (device name/IP) + VLANs + MAC addresses + PoE status. "
                       "Best for: 'What is connected to port X?' questions.",
        "input_schema": {
            "type": "object",
            "properties": {
                "host": {"type": "string", "description": "Switch IP address"},
                "port_id": {"type": "string", "description": "Port identifier (e.g., '1/1/1')"},
            },
            "required": ["host", "port_id"]
        },
        "output_schema": {"type": "object"}
    },
    {
        "name": "aos.interfaces.discover",
        "description": "Discover ALL interfaces on the switch at once. "
                       "Use when: getting switch port inventory, counting active ports, finding available ports. "
                       "Returns: list of all ports with port_id, admin_state, oper_state, speed, type. "
                       "For single port details: use aos.port.discover instead.",
        "input_schema": {
            "type": "object",
            "properties": {
                "host": {"type": "string", "description": "Switch IP address"},
                "include_inactive": {"type": "boolean", "description": "Include down ports", "default": True},
            },
            "required": ["host"]
        },
        "output_schema": {"type": "object"}
    },
]
