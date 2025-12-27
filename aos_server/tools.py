from __future__ import annotations

import string
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from .api_models import RequestContext, ToolInfo
from .authz import authorize_device, authorize_tool
from .config import AppConfig
from .inventory import InventoryStore
from .policy import apply_redactions, compile_policy, sanitize_command, strip_ansi
from .ssh_runner import SSHRunner
from .autodiscover import autodiscover_alcatel_switches
from .poe_parse import parse_show_lanpower
from .routing_parse import (
    parse_show_vrf,
    parse_show_ip_routes,
    parse_show_ip_ospf_interface,
    parse_show_ip_ospf_neighbor,
    parse_show_ip_interface,
    parse_show_ip_ospf_area,
    parse_show_ip_static_routes
)
from .stp_parse import (
    parse_show_spantree_mode,
    parse_show_spantree_cist,
    parse_show_spantree_ports,
    parse_show_spantree_vlan
)

class ArgsDevicesList(BaseModel):
    tags: Optional[List[str]] = None


class DeviceOut(BaseModel):
    id: str
    name: Optional[str] = None
    host: str
    tags: List[str] = Field(default_factory=list)
    facts: Optional[Dict[str, Any]] = None


class OutDevicesList(BaseModel):
    devices: List[DeviceOut]


class ArgsCliReadonly(BaseModel):
    host: str = Field(description="Target switch IP address or hostname")
    command: str
    port: Optional[int] = Field(default=22, description="SSH port")
    username: Optional[str] = Field(default=None, description="SSH username (uses AOS_DEVICE_USERNAME if not provided)")
    timeout_s: Optional[int] = None


class OutCliReadonly(BaseModel):
    host: str
    command: str
    stdout: str
    stderr: str
    exit_status: Optional[int] = None
    duration_ms: int
    truncated: bool = False
    redacted: bool = False


class ArgsPing(BaseModel):
    host: str = Field(description="Target switch IP address or hostname")
    destination: str = Field(description="Ping destination IP or hostname")
    count: Optional[int] = 5
    port: Optional[int] = Field(default=22, description="SSH port")
    timeout_s: Optional[int] = None


class ArgsTraceroute(BaseModel):
    host: str = Field(description="Target switch IP address or hostname")
    destination: str = Field(description="Traceroute destination IP or hostname")
    port: Optional[int] = Field(default=22, description="SSH port")
    timeout_s: Optional[int] = None



class ArgsInventoryAutodiscover(BaseModel):
    seed_device_id: str = Field(description="Device ID of the seed switch (patient zero / core).")
    dns_suffixes: List[str] = Field(default_factory=list, description="Optional DNS suffixes to try when only System Name is available (e.g. ['corp.local']).")
    max_depth: int = 10
    max_devices: int = 200
    collect_facts: bool = True


class DiscoveredDeviceOut(BaseModel):
    host: str
    system_name: Optional[str] = None
    system_description: Optional[str] = None
    via_device_id: Optional[str] = None
    via_local_port: Optional[str] = None
    chassis_id: Optional[str] = Field(default=None, description="LLDP Chassis ID")
    port_id: Optional[str] = Field(default=None, description="LLDP Port ID")
    port_description: Optional[str] = Field(default=None, description="LLDP Port Description")
    management_ip: Optional[str] = Field(default=None, description="LLDP Management Address")


class OutInventoryAutodiscover(BaseModel):
    seed_device_id: str
    discovered: List[DiscoveredDeviceOut]
    added_device_ids: List[str]
    already_present_device_ids: List[str] = Field(default_factory=list)


class ArgsDeviceFacts(BaseModel):
    host: str = Field(description="Target switch IP address or hostname")
    refresh: bool = True
    port: Optional[int] = Field(default=22, description="SSH port")


class DeviceFacts(BaseModel):
    """Structured device facts from OmniSwitch show commands."""
    system_name: Optional[str] = None
    system_description: Optional[str] = None
    model: Optional[str] = None
    serial_number: Optional[str] = None
    software_version: Optional[str] = None
    hardware_revision: Optional[str] = None
    base_mac: Optional[str] = None
    uptime: Optional[str] = None
    contact: Optional[str] = None
    location: Optional[str] = None
    snmp_object_id: Optional[str] = None
    services: Optional[str] = None
    date_time: Optional[str] = None
    part_number: Optional[str] = None
    manufacture_date: Optional[str] = None
    hardware: Optional[Dict[str, Any]] = Field(default=None, description="Hardware details (CPU, RAM, Flash, etc.)")
    lldp: Optional[Dict[str, Any]] = Field(default=None, description="LLDP information")
    raw_facts: Optional[Dict[str, Any]] = Field(default=None, description="Raw unparsed facts")


class OutDeviceFacts(BaseModel):
    host: str
    hostname: Optional[str] = None
    model: Optional[str] = None
    aos_version: Optional[str] = None
    serial_number: Optional[str] = None
    uptime: Optional[str] = None
    mac_address: Optional[str] = None
    facts: DeviceFacts
    duration_ms: int

class ArgsInterfacesDiscover(BaseModel):
    """Discover all interfaces with comprehensive information."""
    host: str = Field(description="Target switch IP address or hostname")
    port: Optional[int] = Field(default=22, description="SSH port")
    include_inactive: bool = Field(default=True, description="Include inactive/down ports")
    include_statistics: bool = Field(default=False, description="Include traffic statistics (slower)")


class ArgsPortDiscover(BaseModel):
    """Discover single port with comprehensive information (optimized)."""
    host: str = Field(description="Target switch IP address or hostname")
    port_id: str = Field(description="Port identifier (e.g., '1/1/1')")
    port: Optional[int] = Field(default=22, description="SSH port")


class VlanInfo(BaseModel):
    """VLAN configuration for a port."""
    untagged: Optional[int] = Field(default=None, description="Untagged VLAN ID")
    tagged: List[int] = Field(default_factory=list, description="Tagged VLAN IDs")
    status: Optional[str] = Field(default=None, description="Port VLAN status (forwarding/inactive)")


class MacAddressEntry(BaseModel):
    """MAC address learned on a port."""
    mac: str = Field(description="MAC address")
    vlan: int = Field(description="VLAN ID")
    type: str = Field(default="dynamic", description="Entry type (dynamic/static)")


class LldpNeighbor(BaseModel):
    """LLDP neighbor information."""
    chassis_id: str = Field(description="Neighbor chassis ID")
    port_id: str = Field(description="Neighbor port ID")
    port_description: Optional[str] = Field(default=None, description="Neighbor port description")
    system_name: Optional[str] = Field(default=None, description="Neighbor system name")
    system_description: Optional[str] = Field(default=None, description="Neighbor system description")
    management_ip: Optional[str] = Field(default=None, description="Neighbor management IP")
    capabilities: Optional[str] = Field(default=None, description="System capabilities")


class PortPoeInfo(BaseModel):
    """PoE information for a port."""
    enabled: bool = Field(description="PoE administratively enabled")
    status: str = Field(description="PoE status (Powered/Searching/Disabled)")
    power_used_mw: int = Field(description="Power consumption in milliwatts")
    max_power_mw: int = Field(description="Maximum power allocation in milliwatts")
    device_class: Optional[str] = Field(default=None, description="Connected device PoE class")
    priority: str = Field(description="PoE priority (Low/High/Critical)")


class PortStatistics(BaseModel):
    """Port traffic statistics."""
    rx_bytes: Optional[int] = Field(default=None, description="Bytes received")
    rx_unicast: Optional[int] = Field(default=None, description="Unicast frames received")
    rx_broadcast: Optional[int] = Field(default=None, description="Broadcast frames received")
    rx_multicast: Optional[int] = Field(default=None, description="Multicast frames received")
    rx_errors: Optional[int] = Field(default=None, description="Receive errors")
    tx_bytes: Optional[int] = Field(default=None, description="Bytes transmitted")
    tx_unicast: Optional[int] = Field(default=None, description="Unicast frames transmitted")
    tx_broadcast: Optional[int] = Field(default=None, description="Broadcast frames transmitted")
    tx_multicast: Optional[int] = Field(default=None, description="Multicast frames transmitted")
    tx_errors: Optional[int] = Field(default=None, description="Transmit errors")


class InterfaceInfo(BaseModel):
    """Complete interface information."""
    port_id: str = Field(description="Port identifier (e.g., 1/1/1)")
    admin_state: str = Field(description="Administrative state (enabled/disabled)")
    oper_state: str = Field(description="Operational state (up/down)")
    speed: Optional[str] = Field(default=None, description="Link speed (e.g., 1000Mbps, 10Gbps)")
    duplex: Optional[str] = Field(default=None, description="Duplex mode (Full/Half)")
    auto_neg: bool = Field(default=True, description="Auto-negotiation enabled")
    
    # Physical layer info
    interface_type: Optional[str] = Field(default=None, description="Interface type (Copper/Fiber)")
    sfp_type: Optional[str] = Field(default=None, description="SFP/XFP module type")
    mac_address: Optional[str] = Field(default=None, description="Port MAC address")
    
    vlan: VlanInfo = Field(description="VLAN configuration")
    mac_addresses: List[MacAddressEntry] = Field(default_factory=list, description="Learned MAC addresses")
    lldp_neighbor: Optional[LldpNeighbor] = Field(default=None, description="LLDP neighbor if present")
    poe: Optional[PortPoeInfo] = Field(default=None, description="PoE information if available")
    
    statistics: Optional[PortStatistics] = Field(default=None, description="Traffic statistics")
    description: Optional[str] = Field(default=None, description="Port description")


class OutInterfacesDiscover(BaseModel):
    """Comprehensive interface discovery output."""
    host: str
    total_ports: int = Field(description="Total number of physical ports")
    active_ports: int = Field(description="Number of operationally up ports")
    ports: List[InterfaceInfo] = Field(description="Detailed information for each port")
    duration_ms: int
    commands_executed: List[str] = Field(description="List of commands executed")


class OutPortDiscover(BaseModel):
    """Single port comprehensive discovery output."""
    host: str
    port: InterfaceInfo = Field(description="Complete port information")
    duration_ms: int
    commands_executed: List[str] = Field(description="List of commands executed")


class ArgsPortInfo(BaseModel):
    """Get detailed information about a specific port."""
    host: str = Field(description="Target switch IP address or hostname")
    port_id: str = Field(description="Port identifier (e.g., '1/1/1')")
    port: Optional[int] = Field(default=22, description="SSH port")


class OutPortInfo(BaseModel):
    """Structured port information."""
    host: str
    port_id: str
    admin_state: Optional[str] = None
    oper_state: Optional[str] = None
    speed: Optional[str] = None
    duplex: Optional[str] = None
    vlan: Optional[str] = None
    description: Optional[str] = None
    mac_address: Optional[str] = None
    mtu: Optional[int] = None
    errors: Optional[Dict[str, Any]] = None
    raw_output: Optional[str] = None
    duration_ms: int


class ArgsPoe(BaseModel):
    host: str = Field(description="Target switch IP address or hostname")
    slot: Optional[str] = Field(
        default=None, 
        description="Slot number (e.g., '1' or '1/1'). If omitted, defaults to slot 1."
    )
    port: Optional[int] = Field(default=22, description="SSH port")


class ArgsPoeRestart(BaseModel):
    """Restart PoE on a specific port (write operation)."""
    host: str = Field(description="Target switch IP address")
    port_id: str = Field(description="Port identifier (e.g., '1/1/12')")
    port: Optional[int] = Field(default=22, description="SSH port")
    username: Optional[str] = Field(default=None, description="SSH username override")
    wait_seconds: Optional[int] = Field(default=5, description="Seconds to wait between stop and start")


class PoePortInfo(BaseModel):
    """Structured PoE port information from OmniSwitch."""
    port_id: str = Field(description="Port identifier (e.g., 1/1/1)")
    max_power_mw: int = Field(description="Maximum power allocation in milliwatts")
    actual_used_mw: int = Field(description="Actual power consumption in milliwatts")
    status: str = Field(description="Port status (e.g., 'Powered', 'Searching', 'Disabled')")
    priority: str = Field(description="PoE priority level (Low, High, Critical)")
    admin_state: str = Field(description="Administrative state (ON/OFF)")
    class_: Optional[str] = Field(default=None, alias="class", description="Device power class")
    type_: Optional[str] = Field(default=None, alias="type", description="PoE type/standard")


class PoEChassisSummary(BaseModel):
    """Chassis-level PoE power budget summary."""
    chassis_id: Optional[int] = None
    slot_id: Optional[int] = None
    max_watts: Optional[int] = Field(default=None, description="Maximum chassis power capacity")
    actual_power_consumed_watts: Optional[int] = Field(default=None, description="Current power consumption")
    power_budget_remaining_watts: Optional[int] = Field(default=None, description="Available power budget")
    total_power_budget_watts: Optional[int] = Field(default=None, description="Total power budget available")
    power_supplies_available: Optional[int] = Field(default=None, description="Number of power supplies")


class OutPoe(BaseModel):
    """Structured PoE diagnostic output."""
    host: str
    command: str
    ports: List[PoePortInfo] = Field(description="Per-port PoE information")
    chassis_summary: PoEChassisSummary = Field(description="Chassis power summary")
    duration_ms: int
    raw_stdout: Optional[str] = Field(default=None, description="Raw CLI output for debugging")


class OutPoeRestart(BaseModel):
    """Result of PoE restart operation."""
    model_config = {"populate_by_name": True}
    
    host: str = Field(description="Switch IP address")
    port_id: str = Field(alias="portId", description="Port that was restarted")
    wait_seconds: int = Field(alias="waitSeconds", description="Wait time between stop/start")
    stop_command: str = Field(alias="stopCommand", description="Command executed to stop PoE")
    start_command: str = Field(alias="startCommand", description="Command executed to start PoE")
    stop_result: str = Field(alias="stopResult", description="Result of stop command")
    start_result: str = Field(alias="startResult", description="Result of start command")
    success: bool = Field(description="Whether restart completed successfully")
    duration_ms: int = Field(alias="durationMs", description="Total operation time in milliseconds")


class ArgsVlanAudit(BaseModel):
    """Arguments for VLAN audit tool."""
    host: str = Field(description="Target switch IP address or hostname")
    vlan_id: Optional[int] = Field(default=None, description="Specific VLAN ID to audit (if omitted, audits all VLANs)")
    port: Optional[int] = Field(default=22, description="SSH port")


class VlanAuditInfo(BaseModel):
    """VLAN configuration information."""
    vlan_id: int = Field(description="VLAN ID")
    name: str = Field(description="VLAN name")
    type: str = Field(description="VLAN type (std, vcm, etc.)")
    admin_state: str = Field(description="Administrative state (Ena/Dis)")
    oper_state: str = Field(description="Operational state (Ena/Dis)")
    ip_routing: Optional[str] = Field(default=None, description="IP routing state")
    mtu: int = Field(description="MTU size")
    mac_tunneling: Optional[str] = Field(default=None, description="MAC tunneling state")


class VlanAuditResult(BaseModel):
    """VLAN audit result."""
    host: str
    total_vlans: int = Field(description="Total number of VLANs configured")
    vlans: List[VlanAuditInfo] = Field(description="List of VLAN configurations")
    summary: Dict[str, int] = Field(description="Summary statistics")
    issues: List[str] = Field(default_factory=list, description="Configuration issues detected")
    duration_ms: int
    commands_executed: List[str]


class ArgsRoutingAudit(BaseModel):
    """Arguments for routing audit tool."""
    host: str = Field(description="Target switch IP address or hostname")
    port: Optional[int] = Field(default=22, description="SSH port")
    include_routes: bool = Field(default=False, description="Include routing table (can be large)")
    route_limit: int = Field(default=100, description="Max number of routes to include if include_routes is true")
    protocol_filter: Optional[str] = Field(default=None, description="Filter routes by protocol (OSPF, STATIC, LOCAL, BGP, etc.)")


class VrfInfo(BaseModel):
    """VRF information."""
    name: str
    profile: str
    protocols: List[str]
    ospf_interfaces: List[Dict[str, Any]] = Field(default_factory=list)
    ospf_neighbors: List[Dict[str, Any]] = Field(default_factory=list)
    ip_interfaces: List[Dict[str, Any]] = Field(default_factory=list)
    ospf_areas: List[Dict[str, Any]] = Field(default_factory=list)


class RoutingAuditResult(BaseModel):
    """Routing audit result."""
    host: str
    vrfs: List[VrfInfo] = Field(description="VRF configurations")
    total_routes: int = Field(default=0, description="Total routes in routing table")
    routes: Optional[List[Dict[str, Any]]] = Field(default=None, description="Sample routes if requested")
    summary: Dict[str, Any] = Field(description="Summary statistics")
    issues: List[str] = Field(default_factory=list, description="Configuration issues detected")
    duration_ms: int
    commands_executed: List[str]


class ArgsSpantreeAudit(BaseModel):
    """Arguments for spanning tree audit tool."""
    host: str = Field(description="Target switch IP address or hostname")
    port: Optional[int] = Field(default=22, description="SSH port")


class SpantreeAuditResult(BaseModel):
    """Spanning tree audit result."""
    host: str
    mode: Dict[str, Any] = Field(description="STP mode configuration")
    cist: Dict[str, Any] = Field(description="Common and Internal Spanning Tree info")
    ports: List[Dict[str, Any]] = Field(description="Per-port STP status")
    vlans: List[Dict[str, Any]] = Field(description="Per-VLAN STP status")
    summary: Dict[str, Any] = Field(description="Summary statistics")
    issues: List[str] = Field(default_factory=list, description="Configuration issues detected")
    duration_ms: int
    commands_executed: List[str]


def _format_template(template: str, values: Dict[str, Any]) -> str:
    # Ensure we only substitute known safe placeholders.
    formatter = string.Formatter()
    fields = [fname for _, fname, _, _ in formatter.parse(template) if fname]
    missing = [f for f in fields if f not in values or values[f] is None]
    if missing:
        raise ValueError(f"Missing required template values: {missing}")
    try:
        return template.format(**values)
    except Exception as e:
        raise ValueError(f"Invalid template formatting: {e}") from e


def call_tool(
    cfg: AppConfig,
    inv: InventoryStore,
    runner: SSHRunner,
    ctx: RequestContext,
    tool: str,
    args: Dict[str, Any],
) -> Dict[str, Any]:
    # No authorization checks - security handled by MCP platform
    # Context (subject, environment) used only for audit logging
    
    compiled_policy = compile_policy(cfg.command_policy)

    # Helper function to create a Device from host/IP
    def create_device_from_host(host: str, port: int = 22, username: Optional[str] = None) -> Any:
        from .config import Device
        return Device(
            id=f"dynamic:{host}",
            host=host,
            port=port,
            name=host,
            tags=[],
            username=username,
        )

    if tool == "aos.cli.readonly":
        parsed = ArgsCliReadonly.model_validate(args)
        device = create_device_from_host(parsed.host, parsed.port or 22, parsed.username)

        cmd = sanitize_command(parsed.command, compiled_policy)
        res = runner.run(device, cmd, timeout_s=parsed.timeout_s)

        stdout = res.stdout
        stderr = res.stderr
        redacted = False

        if compiled_policy.strip_ansi:
            stdout = strip_ansi(stdout)
            stderr = strip_ansi(stderr)

        if cfg.command_policy.redactions:
            stdout2 = apply_redactions(stdout, cfg.command_policy.redactions)
            stderr2 = apply_redactions(stderr, cfg.command_policy.redactions)
            redacted = (stdout2 != stdout) or (stderr2 != stderr)
            stdout, stderr = stdout2, stderr2

        return OutCliReadonly(
            host=device.host,
            command=cmd,
            stdout=stdout,
            stderr=stderr,
            exit_status=res.exit_status,
            duration_ms=res.duration_ms,
            truncated=res.truncated,
            redacted=redacted,
        ).model_dump()

    if tool == "aos.diag.ping":
        parsed = ArgsPing.model_validate(args)
        device = create_device_from_host(parsed.host, parsed.port or 22)

        cmd = _format_template(cfg.templates.ping, {
            "destination": parsed.destination,
            "count": parsed.count,
        })
        cmd = sanitize_command(cmd, compiled_policy)
        res = runner.run(device, cmd, timeout_s=parsed.timeout_s)

        stdout = res.stdout
        stderr = res.stderr
        redacted = False

        if compiled_policy.strip_ansi:
            stdout = strip_ansi(stdout)
            stderr = strip_ansi(stderr)

        if cfg.command_policy.redactions:
            stdout2 = apply_redactions(stdout, cfg.command_policy.redactions)
            stderr2 = apply_redactions(stderr, cfg.command_policy.redactions)
            redacted = (stdout2 != stdout) or (stderr2 != stderr)
            stdout, stderr = stdout2, stderr2

        return OutCliReadonly(
            host=device.host,
            command=cmd,
            stdout=stdout,
            stderr=stderr,
            exit_status=res.exit_status,
            duration_ms=res.duration_ms,
            truncated=res.truncated,
            redacted=redacted,
        ).model_dump()

    if tool == "aos.diag.traceroute":
        parsed = ArgsTraceroute.model_validate(args)
        device = create_device_from_host(parsed.host, parsed.port or 22)

        cmd = _format_template(cfg.templates.traceroute, {
            "destination": parsed.destination,
        })
        cmd = sanitize_command(cmd, compiled_policy)
        res = runner.run(device, cmd, timeout_s=parsed.timeout_s)

        stdout = res.stdout
        stderr = res.stderr
        redacted = False

        if compiled_policy.strip_ansi:
            stdout = strip_ansi(stdout)
            stderr = strip_ansi(stderr)

        if cfg.command_policy.redactions:
            stdout2 = apply_redactions(stdout, cfg.command_policy.redactions)
            stderr2 = apply_redactions(stderr, cfg.command_policy.redactions)
            redacted = (stdout2 != stdout) or (stderr2 != stderr)
            stdout, stderr = stdout2, stderr2

        return OutCliReadonly(
            host=device.host,
            command=cmd,
            stdout=stdout,
            stderr=stderr,
            exit_status=res.exit_status,
            duration_ms=res.duration_ms,
            truncated=res.truncated,
            redacted=redacted,
        ).model_dump()

    if tool == "aos.diag.poe":
        parsed = ArgsPoe.model_validate(args)
        device = create_device_from_host(parsed.host, parsed.port or 22)
        
        # Build command
        if parsed.slot:
            slot_num = parsed.slot.split('/')[0]
            raw_cmd = f"show lanpower slot {slot_num}/1"
        else:
            raw_cmd = "show lanpower slot 1/1"

        # Validate and execute
        cmd = sanitize_command(raw_cmd, compiled_policy)
        res = runner.run(device, cmd)
        
        # Parse structured output
        parsed_poe = parse_show_lanpower(res.stdout)
        
        # Build structured response
        ports = [PoePortInfo(**p) for p in parsed_poe["ports"]]
        chassis_summary = PoEChassisSummary(**parsed_poe["chassis_summary"])
        
        return OutPoe(
            host=device.host,
            command=cmd,
            ports=ports,
            chassis_summary=chassis_summary,
            duration_ms=res.duration_ms,
            raw_stdout=None,
        ).model_dump(by_alias=True)

    if tool == "aos.poe.restart":
        import time
        
        parsed = ArgsPoeRestart.model_validate(args)
        device = create_device_from_host(parsed.host, parsed.port or 22, parsed.username)
        
        start_time = time.time()
        
        # Build disable command
        stop_cmd_raw = f"lanpower port {parsed.port_id} admin-state disable"
        stop_cmd = sanitize_command(stop_cmd_raw, compiled_policy)
        
        # Execute disable
        stop_res = runner.run(device, stop_cmd)
        
        # Wait
        time.sleep(parsed.wait_seconds or 5)
        
        # Build enable command
        start_cmd_raw = f"lanpower port {parsed.port_id} admin-state enable"
        start_cmd = sanitize_command(start_cmd_raw, compiled_policy)
        
        # Execute enable
        start_res = runner.run(device, start_cmd)
        
        # Calculate total duration
        duration_ms = int((time.time() - start_time) * 1000)
        
        # Determine success (both commands should have exit_status 0)
        success = stop_res.exit_status == 0 and start_res.exit_status == 0
        
        return OutPoeRestart(
            host=device.host,
            port_id=parsed.port_id,
            wait_seconds=parsed.wait_seconds or 5,
            stop_command=stop_cmd,
            start_command=start_cmd,
            stop_result=stop_res.stdout.strip() if stop_res.stdout else "OK",
            start_result=start_res.stdout.strip() if start_res.stdout else "OK",
            success=success,
            duration_ms=duration_ms,
        ).model_dump(by_alias=True)

    if tool == "aos.device.facts":
        import re
        parsed = ArgsDeviceFacts.model_validate(args)
        device = create_device_from_host(parsed.host, parsed.port or 22)
        
        import time
        start_time = time.time()
        
        # Run multiple show commands to gather facts
        commands = [
            "show system",
            "show chassis",
            "show microcode",
        ]
        
        results = {}
        for cmd in commands:
            safe_cmd = sanitize_command(cmd, compiled_policy)
            res = runner.run(device, safe_cmd)
            results[cmd] = res.stdout
        
        # Parse results with AOS-specific format
        facts = DeviceFacts()
        system_output = results.get("show system", "")
        chassis_output = results.get("show chassis", "")
        
        # Parse system name (format: "Name:         HOSTNAME,")
        name_match = re.search(r'^\s*Name\s*:\s*(.+?),?\s*$', system_output, re.MULTILINE | re.IGNORECASE)
        if name_match:
            facts.system_name = name_match.group(1).strip().rstrip(',')
        
        # Parse description (contains model and version)
        # Format: "Description:  Alcatel-Lucent Enterprise OS6860-P24 8.9.94.R04 GA, March 28, 2024.,"
        desc_match = re.search(r'^\s*Description\s*:\s*(.+?),?\s*$', system_output, re.MULTILINE | re.IGNORECASE)
        if desc_match:
            desc = desc_match.group(1).strip().rstrip(',')
            facts.system_description = desc
            
            # Extract model (e.g., OS6860-P24)
            model_match = re.search(r'(OS\d+[A-Z0-9-]+)', desc)
            if model_match:
                facts.model = model_match.group(1)
            
            # Extract software version (e.g., 8.9.94.R04)
            version_match = re.search(r'([\d]+\.[\d]+\.[\d]+\.R[\d]+)', desc)
            if version_match:
                facts.software_version = version_match.group(1)
        
        # Parse Object ID
        oid_match = re.search(r'^\s*Object ID\s*:\s*(.+?),?\s*$', system_output, re.MULTILINE | re.IGNORECASE)
        if oid_match:
            facts.snmp_object_id = oid_match.group(1).strip().rstrip(',')
        
        # Parse uptime
        uptime_match = re.search(r'^\s*Up Time\s*:\s*(.+?),?\s*$', system_output, re.MULTILINE | re.IGNORECASE)
        if uptime_match:
            facts.uptime = uptime_match.group(1).strip().rstrip(',')
        
        # Parse contact
        contact_match = re.search(r'^\s*Contact\s*:\s*(.+?),?\s*$', system_output, re.MULTILINE | re.IGNORECASE)
        if contact_match:
            facts.contact = contact_match.group(1).strip().rstrip(',')
        
        # Parse location
        location_match = re.search(r'^\s*Location\s*:\s*(.+?),?\s*$', system_output, re.MULTILINE | re.IGNORECASE)
        if location_match:
            facts.location = location_match.group(1).strip().rstrip(',')
        
        # Parse services
        services_match = re.search(r'^\s*Services\s*:\s*(.+?),?\s*$', system_output, re.MULTILINE | re.IGNORECASE)
        if services_match:
            facts.services = services_match.group(1).strip().rstrip(',')
        
        # Parse date/time
        datetime_match = re.search(r'^\s*Date & Time\s*:\s*(.+?)\s*$', system_output, re.MULTILINE | re.IGNORECASE)
        if datetime_match:
            facts.date_time = datetime_match.group(1).strip()
        
        # Parse chassis output for serial, MAC, hardware details, etc.
        if chassis_output:
            # Serial Number
            serial_match = re.search(r'^\s*Serial Number\s*:\s*(\S+)', chassis_output, re.MULTILINE | re.IGNORECASE)
            if serial_match:
                facts.serial_number = serial_match.group(1).rstrip(',')
            
            # MAC Address
            mac_match = re.search(r'^\s*MAC Address\s*:\s*([0-9a-fA-F:]+)', chassis_output, re.MULTILINE | re.IGNORECASE)
            if mac_match:
                facts.base_mac = mac_match.group(1)
            
            # Part Number
            part_match = re.search(r'^\s*Part Number\s*:\s*(.+?),?\s*$', chassis_output, re.MULTILINE | re.IGNORECASE)
            if part_match:
                facts.part_number = part_match.group(1).strip().rstrip(',')
            
            # Hardware Revision
            hw_rev_match = re.search(r'^\s*Hardware Revision\s*:\s*(\S+)', chassis_output, re.MULTILINE | re.IGNORECASE)
            if hw_rev_match:
                facts.hardware_revision = hw_rev_match.group(1).rstrip(',')
            
            # Manufacture Date
            mfg_date_match = re.search(r'^\s*Manufacture Date\s*:\s*(.+?),?\s*$', chassis_output, re.MULTILINE | re.IGNORECASE)
            if mfg_date_match:
                facts.manufacture_date = mfg_date_match.group(1).strip().rstrip(',')
        
        duration_ms = int((time.time() - start_time) * 1000)
        
        return OutDeviceFacts(
            host=device.host,
            hostname=facts.system_name,
            model=facts.model,
            aos_version=facts.software_version,
            serial_number=facts.serial_number,
            uptime=facts.uptime,
            mac_address=facts.base_mac,
            facts=facts,
            duration_ms=duration_ms,
        ).model_dump()
    
    if tool == "aos.port.info":
        import re
        parsed = ArgsPortInfo.model_validate(args)
        device = create_device_from_host(parsed.host, parsed.port or 22)
        
        import time
        start_time = time.time()
        
        # Get port information
        cmd = f"show interfaces port {parsed.port_id}"
        safe_cmd = sanitize_command(cmd, compiled_policy)
        res = runner.run(device, safe_cmd)
        
        output = res.stdout
        
        # Parse output
        admin_state = None
        oper_state = None
        speed = None
        duplex = None
        vlan = None
        
        admin_match = re.search(r'Admin State\s*[:\-]\s*(\S+)', output, re.IGNORECASE)
        if admin_match:
            admin_state = admin_match.group(1)
        
        oper_match = re.search(r'Operational Status\s*[:\-]\s*(\S+)', output, re.IGNORECASE)
        if not oper_match:
            oper_match = re.search(r'Link State\s*[:\-]\s*(\S+)', output, re.IGNORECASE)
        if oper_match:
            oper_state = oper_match.group(1)
        
        speed_match = re.search(r'Speed\s*[:\-]\s*(.+?)[\r\n]', output, re.IGNORECASE)
        if speed_match:
            speed = speed_match.group(1).strip()
        
        duplex_match = re.search(r'Duplex\s*[:\-]\s*(\S+)', output, re.IGNORECASE)
        if duplex_match:
            duplex = duplex_match.group(1)
        
        vlan_match = re.search(r'VLAN\s*[:\-]\s*(\S+)', output, re.IGNORECASE)
        if vlan_match:
            vlan = vlan_match.group(1)
        
        duration_ms = int((time.time() - start_time) * 1000)
        
        return OutPortInfo(
            host=device.host,
            port_id=parsed.port_id,
            admin_state=admin_state,
            oper_state=oper_state,
            speed=speed,
            duplex=duplex,
            vlan=vlan,
            raw_output=output if not output else None,  # Include raw for debugging
            duration_ms=duration_ms,
        ).model_dump()
    
    if tool == "aos.interfaces.discover":
        import time
        from .interface_parse import (
            parse_interfaces_status,
            parse_vlan_members,
            parse_mac_learning,
            parse_lldp_remote,
            parse_show_interfaces_all_detailed,  # NEW: for statistics
            aggregate_interface_data
        )
        
        parsed = ArgsInterfacesDiscover.model_validate(args)
        device = create_device_from_host(parsed.host, parsed.port or 22)
        
        start_time = time.time()
        commands_executed = []
        
        # Execute discovery commands
        commands = [
            "show interfaces status",
            "show vlan members",
            "show mac-learning",
            "show lldp remote-system"
        ]
        
        # Add statistics command if requested
        if parsed.include_statistics:
            commands.insert(1, "show interfaces")  # Add after status
        
        # Add PoE command if switch supports it (detect from model or try)
        try:
            poe_cmd = "show lanpower slot 1/1"
            poe_safe = sanitize_command(poe_cmd, compiled_policy)
            poe_res = runner.run(device, poe_safe, timeout_s=10)
            if poe_res.exit_status == 0 and "lanpower" in poe_res.stdout.lower():
                commands.append(poe_cmd)
        except:
            pass  # PoE not supported
        
        results = {}
        for cmd in commands:
            safe_cmd = sanitize_command(cmd, compiled_policy)
            res = runner.run(device, safe_cmd, timeout_s=30)
            results[cmd] = res.stdout
            commands_executed.append(cmd)
        
        # Parse each command output
        status_data = parse_interfaces_status(results.get("show interfaces status", ""))
        vlan_data = parse_vlan_members(results.get("show vlan members", ""))
        mac_data = parse_mac_learning(results.get("show mac-learning", ""))
        lldp_data = parse_lldp_remote(results.get("show lldp remote-system", ""))
        
        # Parse detailed info (stats, SFP, etc.) if requested
        detailed_data = {}
        if parsed.include_statistics and "show interfaces" in results:
            detailed_data = parse_show_interfaces_all_detailed(results["show interfaces"])
        
        # Parse PoE if available
        poe_data = None
        if "show lanpower slot 1/1" in results:
            try:
                parsed_poe = parse_show_lanpower(results["show lanpower slot 1/1"])
                # Convert to dict keyed by port_id
                poe_data = {}
                for port_info in parsed_poe.get("ports", []):
                    poe_data[port_info["port_id"]] = port_info
            except:
                pass  # PoE parsing failed
        
        # Aggregate all data (including detailed if requested)
        interfaces_list = aggregate_interface_data(
            status_data, vlan_data, mac_data, lldp_data, poe_data, detailed_data
        )
        
        # Filter inactive ports if requested
        if not parsed.include_inactive:
            interfaces_list = [p for p in interfaces_list if p["oper_state"] == "up"]
        
        # Convert to Pydantic models
        ports = []
        for iface_dict in interfaces_list:
            # Build VlanInfo
            vlan_info = VlanInfo(
                untagged=iface_dict["vlan"]["untagged"],
                tagged=iface_dict["vlan"]["tagged"],
                status=iface_dict["vlan"].get("status")
            )
            
            # Build MAC entries
            mac_entries = [MacAddressEntry(**m) for m in iface_dict["mac_addresses"]]
            
            # Build LLDP neighbor
            lldp_neighbor = None
            if iface_dict["lldp_neighbor"]:
                lldp_neighbor = LldpNeighbor(**iface_dict["lldp_neighbor"])
            
            # Build PoE info
            poe_info = None
            if iface_dict["poe"]:
                poe_info = PortPoeInfo(**iface_dict["poe"])
            
            # Build statistics if available
            port_stats = None
            if iface_dict.get("statistics"):
                port_stats = PortStatistics(**iface_dict["statistics"])
            
            # Build InterfaceInfo
            port_info = InterfaceInfo(
                port_id=iface_dict["port_id"],
                admin_state=iface_dict["admin_state"],
                oper_state=iface_dict["oper_state"],
                speed=iface_dict["speed"],
                duplex=iface_dict["duplex"],
                auto_neg=iface_dict["auto_neg"],
                interface_type=iface_dict.get("interface_type"),
                sfp_type=iface_dict.get("sfp_type"),
                mac_address=iface_dict.get("mac_address"),
                vlan=vlan_info,
                mac_addresses=mac_entries,
                lldp_neighbor=lldp_neighbor,
                poe=poe_info,
                statistics=port_stats,
                description=iface_dict["description"]
            )
            ports.append(port_info)
        
        duration_ms = int((time.time() - start_time) * 1000)
        total_ports = len(ports)
        active_ports = sum(1 for p in ports if p.oper_state == "up")
        
        return OutInterfacesDiscover(
            host=device.host,
            total_ports=total_ports,
            active_ports=active_ports,
            ports=ports,
            duration_ms=duration_ms,
            commands_executed=commands_executed
        ).model_dump()
    
    if tool == "aos.port.discover":
        import time
        from .interface_parse import (
            parse_interfaces_status,  # Status format (table) - has admin state
            parse_show_interfaces_detailed,  # Detailed format - has SFP, stats
            parse_vlan_members_port,
            parse_mac_learning,
            parse_lldp_remote
        )
        
        parsed = ArgsPortDiscover.model_validate(args)
        device = create_device_from_host(parsed.host, parsed.port or 22)
        
        start_time = time.time()
        commands_executed = []
        
        # Execute optimized port-specific commands
        commands = [
            f"show interfaces {parsed.port_id} status",  # Status format for admin state
            f"show interfaces {parsed.port_id}",          # Detailed format for SFP/stats
            f"show vlan members port {parsed.port_id}",
            f"show mac-learning port {parsed.port_id}",
            f"show lldp port {parsed.port_id} remote-system"
        ]
        
        results = {}
        for cmd in commands:
            safe_cmd = sanitize_command(cmd, compiled_policy)
            res = runner.run(device, safe_cmd, timeout_s=10)
            # Store with a simple key based on command type
            if "status" in cmd:
                results["status"] = res.stdout
            elif "interfaces" in cmd and "status" not in cmd:
                results["detailed"] = res.stdout
            elif "vlan" in cmd:
                results["vlan"] = res.stdout
            elif "mac-learning" in cmd:
                results["mac"] = res.stdout
            elif "lldp" in cmd:
                results["lldp"] = res.stdout
            commands_executed.append(cmd)
        
        # Parse each command output
        status_output = results.get("status", "")
        vlan_output = results.get("vlan", "")
        mac_output = results.get("mac", "")
        lldp_output = results.get("lldp", "")
        
        # Use table status parser (returns dict keyed by port_id)
        status_data = parse_interfaces_status(status_output)
        status_dict = status_data.get(parsed.port_id, {
            "admin_state": "unknown",
            "oper_state": "unknown",
            "speed": None,
            "duplex": None,
            "auto_neg": True
        })
        vlan_list = parse_vlan_members_port(vlan_output, parsed.port_id)
        mac_data = parse_mac_learning(mac_output)
        lldp_data = parse_lldp_remote(lldp_output)
        
        # Parse detailed info (SFP, interface type, statistics)
        detailed_output = results.get("detailed", "")
        detailed_info = parse_show_interfaces_detailed(detailed_output, parsed.port_id)
        
        # VLAN info (vlan_list is already a list for this port)
        vlan_info = VlanInfo()
        for vlan_id, vlan_type, vlan_status in vlan_list:
            if vlan_type == "untagged":
                vlan_info.untagged = vlan_id
                vlan_info.status = vlan_status
            elif vlan_type == "tagged":
                vlan_info.tagged.append(vlan_id)
        
        # MAC addresses
        mac_entries = []
        if parsed.port_id in mac_data:
            for mac, vlan in mac_data[parsed.port_id]:
                mac_entries.append(MacAddressEntry(mac=mac, vlan=vlan, type="dynamic"))
        
        # LLDP neighbor
        lldp_neighbor = None
        if parsed.port_id in lldp_data:
            neighbor = lldp_data[parsed.port_id]
            lldp_neighbor = LldpNeighbor(**neighbor)
        
        # PoE (try to get it - must use slot command and filter)
        poe_info = None
        try:
            # Extract slot from port_id (e.g., 1/1/19 -> slot 1/1)
            port_parts = parsed.port_id.split('/')
            if len(port_parts) >= 2:
                slot = f"{port_parts[0]}/{port_parts[1]}"
                poe_cmd = f"show lanpower slot {slot}"
                poe_safe = sanitize_command(poe_cmd, compiled_policy)
                poe_res = runner.run(device, poe_safe, timeout_s=5)
                if poe_res.exit_status == 0:
                    parsed_poe = parse_show_lanpower(poe_res.stdout)
                    # Find the specific port in the results
                    for port_poe in parsed_poe.get("ports", []):
                        if port_poe["port_id"] == parsed.port_id:
                            poe_info = PortPoeInfo(
                                enabled=port_poe["admin_state"] == "ON",
                                status=port_poe["status"],
                                power_used_mw=port_poe["actual_used_mw"],
                                max_power_mw=port_poe["max_power_mw"],
                                device_class=port_poe.get("class_"),
                                priority=port_poe["priority"]
                            )
                            commands_executed.append(poe_cmd)
                            break
        except:
            pass  # PoE not available
        
        # Build statistics if available
        port_stats = None
        if detailed_info.get("statistics"):
            port_stats = PortStatistics(**detailed_info["statistics"])
        
        port_info = InterfaceInfo(
            port_id=parsed.port_id,
            admin_state=status_dict.get("admin_state", "unknown"),
            oper_state=status_dict.get("oper_state", "down"),
            speed=status_dict.get("speed"),
            duplex=status_dict.get("duplex"),
            auto_neg=status_dict.get("auto_neg", True),
            interface_type=detailed_info.get("interface_type"),
            sfp_type=detailed_info.get("sfp_type"),
            mac_address=detailed_info.get("mac_address"),
            vlan=vlan_info,
            mac_addresses=mac_entries,
            lldp_neighbor=lldp_neighbor,
            poe=poe_info,
            statistics=port_stats,
            description=None
        )
        
        duration_ms = int((time.time() - start_time) * 1000)
        
        return OutPortDiscover(
            host=device.host,
            port=port_info,
            duration_ms=duration_ms,
            commands_executed=commands_executed
        ).model_dump()

    if tool == "aos.vlan.audit":
        import time
        from .vlan_parse import parse_show_vlan, parse_show_vlan_detail, analyze_vlan_config
        
        parsed = ArgsVlanAudit.model_validate(args)
        device = create_device_from_host(parsed.host, parsed.port or 22)
        
        start_time = time.time()
        commands_executed = []
        
        # Determine which commands to run
        if parsed.vlan_id:
            # Audit specific VLAN
            commands = [
                "show vlan",  # Get list to validate VLAN exists
                f"show vlan {parsed.vlan_id}"
            ]
        else:
            # Audit all VLANs
            commands = ["show vlan"]
        
        results = {}
        for cmd in commands:
            safe_cmd = sanitize_command(cmd, compiled_policy)
            res = runner.run(device, safe_cmd, timeout_s=15)
            results[cmd] = res.stdout
            commands_executed.append(cmd)
        
        # Parse show vlan output
        vlan_list_output = results.get("show vlan", "")
        vlans = parse_show_vlan(vlan_list_output)
        
        # If specific VLAN requested, enrich with detailed info
        if parsed.vlan_id:
            detail_cmd = f"show vlan {parsed.vlan_id}"
            if detail_cmd in results:
                detail = parse_show_vlan_detail(results[detail_cmd])
                # Find the VLAN in the list and update it
                for vlan in vlans:
                    if vlan['vlan_id'] == parsed.vlan_id:
                        vlan.update({
                            'mac_tunneling': detail.get('mac_tunneling')
                        })
                        break
                
                # Filter to only requested VLAN
                vlans = [v for v in vlans if v['vlan_id'] == parsed.vlan_id]
        
        # Analyze configuration
        summary, issues = analyze_vlan_config(vlans)
        
        duration_ms = int((time.time() - start_time) * 1000)
        
        # Build Pydantic models
        vlan_infos = []
        for vlan_dict in vlans:
            vlan_info = VlanAuditInfo(
                vlan_id=vlan_dict['vlan_id'],
                name=vlan_dict['name'],
                type=vlan_dict['type'],
                admin_state=vlan_dict['admin_state'],
                oper_state=vlan_dict['oper_state'],
                ip_routing=vlan_dict.get('ip_routing'),
                mtu=vlan_dict['mtu'],
                mac_tunneling=vlan_dict.get('mac_tunneling')
            )
            vlan_infos.append(vlan_info)
        
        result = VlanAuditResult(
            host=device.host,
            total_vlans=len(vlan_infos),
            vlans=vlan_infos,
            summary=summary,
            issues=issues,
            duration_ms=duration_ms,
            commands_executed=commands_executed
        )
        
        # Generate formatted content for display
        content_parts = []
        
        if parsed.vlan_id:
            # Single VLAN detail
            if vlan_infos:
                v = vlan_infos[0]
                content_parts.append({
                    "type": "text",
                    "text": f"**VLAN {v.vlan_id}: {v.name}**\n\n"
                           f"Type: {v.type}\n"
                           f"Admin State: {v.admin_state}\n"
                           f"Oper State: {v.oper_state}\n"
                           f"IP Routing: {v.ip_routing}\n"
                           f"MTU: {v.mtu}\n"
                           f"MAC Tunneling: {v.mac_tunneling}\n"
                })
                if issues:
                    content_parts.append({
                        "type": "text",
                        "text": f"\n⚠️ Issues:\n" + "\n".join(f"- {issue}" for issue in issues)
                    })
        else:
            # Summary of all VLANs
            content_parts.append({
                "type": "text",
                "text": f"**VLAN Audit Report: {device.host}**\n\n"
                       f"Total VLANs: {summary['total']}\n"
                       f"Enabled: {summary['enabled']} | Disabled: {summary['disabled']}\n"
                       f"Operational: {summary['operational']} | Down: {summary['down']}\n"
                       f"With IP Routing: {summary['with_ip_routing']}\n"
                       f"Standard: {summary['std_vlans']} | VCM: {summary['vcm_vlans']}\n"
            })
            
            if issues:
                content_parts.append({
                    "type": "text",
                    "text": f"\n⚠️ Configuration Issues Detected ({len(issues)}):\n" + 
                           "\n".join(f"{i+1}. {issue}" for i, issue in enumerate(issues[:10]))
                })
                if len(issues) > 10:
                    content_parts.append({
                        "type": "text",
                        "text": f"\n... and {len(issues) - 10} more issues"
                    })
        
        return {
            **result.model_dump(),
            "content": content_parts
        }
    
    if tool == "aos.routing.audit":
        import time
        
        parsed = ArgsRoutingAudit.model_validate(args)
        device = create_device_from_host(parsed.host, parsed.port or 22)
        
        start_time = time.time()
        commands_executed = []
        issues = []
        
        # Get VRF list
        vrf_cmd = "show vrf"
        safe_cmd = sanitize_command(vrf_cmd, compiled_policy)
        vrf_result = runner.run(device, safe_cmd, timeout_s=15)
        commands_executed.append(vrf_cmd)
        
        vrfs_data = parse_show_vrf(vrf_result.stdout)
        
        # Get routing table summary
        routes_data = None
        total_routes = 0
        if parsed.include_routes:
            routes_cmd = f"show ip routes | head -n {parsed.route_limit + 20}"
            safe_cmd = sanitize_command(routes_cmd, compiled_policy)
            routes_result = runner.run(device, safe_cmd, timeout_s=15)
            commands_executed.append(routes_cmd)
            routes_data = parse_show_ip_routes(routes_result.stdout, limit=parsed.route_limit, protocol_filter=parsed.protocol_filter)
            total_routes = routes_data.get('total_routes', 0)
        
        # For each VRF, get OSPF and IP interface info
        vrf_infos = []
        for vrf in vrfs_data:
            vrf_name = vrf['name']
            
            ospf_interfaces = []
            ospf_neighbors = []
            ip_interfaces = []
            ospf_areas = []
            
            # Check if VRF has OSPF
            if 'OSPF' in vrf['protocols']:
                # Get OSPF areas
                if vrf_name == 'default':
                    ospf_area_cmd = "show ip ospf area"
                else:
                    ospf_area_cmd = f'vrf {vrf_name} show ip ospf area'
                
                safe_cmd = sanitize_command(ospf_area_cmd, compiled_policy)
                try:
                    ospf_area_result = runner.run(device, safe_cmd, timeout_s=15)
                    commands_executed.append(ospf_area_cmd)
                    ospf_areas = parse_show_ip_ospf_area(ospf_area_result.stdout)
                except Exception as e:
                    pass  # Areas not critical
                # Get OSPF interfaces
                if vrf_name == 'default':
                    ospf_int_cmd = "show ip ospf interface"
                else:
                    ospf_int_cmd = f'vrf {vrf_name} show ip ospf interface'
                
                safe_cmd = sanitize_command(ospf_int_cmd, compiled_policy)
                try:
                    ospf_int_result = runner.run(device, safe_cmd, timeout_s=15)
                    commands_executed.append(ospf_int_cmd)
                    ospf_interfaces = parse_show_ip_ospf_interface(ospf_int_result.stdout)
                    
                    # Check for down OSPF interfaces
                    for iface in ospf_interfaces:
                        if iface.get('oper_status') == 'down':
                            issues.append(f"VRF {vrf_name}: OSPF interface {iface.get('interface')} is operationally down")
                        if iface.get('admin_status') == 'disabled':
                            issues.append(f"VRF {vrf_name}: OSPF interface {iface.get('interface')} is administratively disabled")
                
                except Exception as e:
                    issues.append(f"VRF {vrf_name}: Failed to get OSPF interfaces - {str(e)}")
                
                # Get OSPF neighbors  
                if vrf_name == 'default':
                    ospf_nbr_cmd = "show ip ospf neighbor"
                else:
                    ospf_nbr_cmd = f'vrf {vrf_name} show ip ospf neighbor'
                
                safe_cmd = sanitize_command(ospf_nbr_cmd, compiled_policy)
                try:
                    ospf_nbr_result = runner.run(device, safe_cmd, timeout_s=15)
                    commands_executed.append(ospf_nbr_cmd)
                    ospf_neighbors = parse_show_ip_ospf_neighbor(ospf_nbr_result.stdout)
                    
                    # Check neighbor states
                    for nbr in ospf_neighbors:
                        if nbr.get('state') not in ['Full', 'TwoWay']:
                            issues.append(f"VRF {vrf_name}: OSPF neighbor {nbr.get('router_id')} in state {nbr.get('state')}")
                
                except Exception as e:
                    issues.append(f"VRF {vrf_name}: Failed to get OSPF neighbors - {str(e)}")
            
            # Get IP interfaces for this VRF
            if vrf_name == 'default':
                ip_int_cmd = "show ip interface"
            else:
                ip_int_cmd = f'vrf {vrf_name} show ip interface'
            
            safe_cmd = sanitize_command(ip_int_cmd, compiled_policy)
            try:
                ip_int_result = runner.run(device, safe_cmd, timeout_s=15)
                commands_executed.append(ip_int_cmd)
                ip_interfaces = parse_show_ip_interface(ip_int_result.stdout)
                
                # Check for down IP interfaces
                for iface in ip_interfaces:
                    if iface.get('oper_status') == 'disabled' or iface.get('state') == 'down':
                        issues.append(f"VRF {vrf_name}: IP interface {iface.get('interface')} is down")
            
            except Exception as e:
                issues.append(f"VRF {vrf_name}: Failed to get IP interfaces - {str(e)}")
            
            vrf_info = VrfInfo(
                name=vrf_name,
                profile=vrf['profile'],
                protocols=vrf['protocols'],
                ospf_interfaces=ospf_interfaces,
                ospf_neighbors=ospf_neighbors,
                ip_interfaces=ip_interfaces,
                ospf_areas=ospf_areas
            )
            vrf_infos.append(vrf_info)
        
        # Build summary
        total_ospf_interfaces = sum(len(v.ospf_interfaces) for v in vrf_infos)
        total_ospf_neighbors = sum(len(v.ospf_neighbors) for v in vrf_infos)
        total_ip_interfaces = sum(len(v.ip_interfaces) for v in vrf_infos)
        
        summary = {
            'total_vrfs': len(vrf_infos),
            'vrfs_with_ospf': len([v for v in vrf_infos if 'OSPF' in v.protocols]),
            'total_ospf_interfaces': total_ospf_interfaces,
            'total_ospf_neighbors': total_ospf_neighbors,
            'total_ip_interfaces': total_ip_interfaces,
            'total_routes': total_routes
        }
        
        duration_ms = int((time.time() - start_time) * 1000)
        
        result = RoutingAuditResult(
            host=device.host,
            vrfs=vrf_infos,
            total_routes=total_routes,
            routes=routes_data.get('routes') if routes_data else None,
            summary=summary,
            issues=issues,
            duration_ms=duration_ms,
            commands_executed=commands_executed
        )
        
        # Generate content
        content_parts = []
        content_parts.append({
            "type": "text",
            "text": f"**Routing Audit Report: {device.host}**\n\n"
                   f"VRFs: {summary['total_vrfs']}\n"
                   f"VRFs with OSPF: {summary['vrfs_with_ospf']}\n"
                   f"OSPF Interfaces: {summary['total_ospf_interfaces']}\n"
                   f"OSPF Neighbors: {summary['total_ospf_neighbors']}\n"
                   f"IP Interfaces: {summary['total_ip_interfaces']}\n"
                   f"Total Routes: {summary['total_routes']}\n"
        })
        
        if issues:
            content_parts.append({
                "type": "text",
                "text": f"\n⚠️ Issues Detected ({len(issues)}):\n" + 
                       "\n".join(f"{i+1}. {issue}" for i, issue in enumerate(issues[:10]))
            })
            if len(issues) > 10:
                content_parts.append({
                    "type": "text",
                    "text": f"\n... and {len(issues) - 10} more issues"
                })
        
        return {
            **result.model_dump(),
            "content": content_parts
        }
    
    if tool == "aos.spantree.audit":
        import time
        
        parsed = ArgsSpantreeAudit.model_validate(args)
        device = create_device_from_host(parsed.host, parsed.port or 22)
        
        start_time = time.time()
        commands_executed = []
        issues = []
        
        # Get STP mode
        mode_cmd = "show spantree mode"
        safe_cmd = sanitize_command(mode_cmd, compiled_policy)
        mode_result = runner.run(device, safe_cmd, timeout_s=15)
        commands_executed.append(mode_cmd)
        mode_data = parse_show_spantree_mode(mode_result.stdout)
        
        # Get CIST (Common and Internal Spanning Tree)
        cist_cmd = "show spantree cist"
        safe_cmd = sanitize_command(cist_cmd, compiled_policy)
        cist_result = runner.run(device, safe_cmd, timeout_s=15)
        commands_executed.append(cist_cmd)
        cist_data = parse_show_spantree_cist(cist_result.stdout)
        
        # Get STP ports status
        ports_cmd = "show spantree ports"
        safe_cmd = sanitize_command(ports_cmd, compiled_policy)
        ports_result = runner.run(device, safe_cmd, timeout_s=15)
        commands_executed.append(ports_cmd)
        ports_data = parse_show_spantree_ports(ports_result.stdout)
        
        # Get VLAN STP status
        vlan_cmd = "show spantree vlan"
        safe_cmd = sanitize_command(vlan_cmd, compiled_policy)
        vlan_result = runner.run(device, safe_cmd, timeout_s=15)
        commands_executed.append(vlan_cmd)
        vlan_data = parse_show_spantree_vlan(vlan_result.stdout)
        
        duration_ms = int((time.time() - start_time) * 1000)
        
        # Detect issues
        if cist_data.get('stp_status') != 'ON':
            issues.append("Spanning Tree is disabled globally")
        
        if cist_data.get('bridge_id') == cist_data.get('designated_root'):
            issues.append("This switch is the root bridge - verify this is intentional")
        
        # Check for ports in non-forwarding state
        for port in ports_data:
            if port['oper_status'] not in ['FORW', 'DIS']:
                issues.append(f"Port {port['port_id']} in unusual state: {port['oper_status']}")
            if port['role'] == 'ROOT' and port['oper_status'] != 'FORW':
                issues.append(f"Root port {port['port_id']} is not forwarding")
        
        # Check VLANs with STP OFF
        for vlan in vlan_data:
            if vlan['status'] == 'OFF':
                issues.append(f"VLAN {vlan['vlan_id']} has STP disabled")
        
        # Summary
        total_ports = len(ports_data)
        forwarding_ports = sum(1 for p in ports_data if p['oper_status'] == 'FORW')
        blocking_ports = sum(1 for p in ports_data if p['oper_status'] not in ['FORW', 'DIS'])
        total_vlans = len(vlan_data)
        vlans_stp_on = sum(1 for v in vlan_data if v['status'] == 'ON')
        
        summary = {
            'total_ports': total_ports,
            'forwarding_ports': forwarding_ports,
            'blocking_ports': blocking_ports,
            'disabled_ports': total_ports - forwarding_ports - blocking_ports,
            'total_vlans': total_vlans,
            'vlans_stp_enabled': vlans_stp_on,
            'vlans_stp_disabled': total_vlans - vlans_stp_on,
            'is_root_bridge': cist_data.get('bridge_id') == cist_data.get('designated_root'),
            'topology_changes': cist_data.get('topology_changes', 0)
        }
        
        result = SpantreeAuditResult(
            host=device.host,
            mode=mode_data,
            cist=cist_data,
            ports=ports_data,
            vlans=vlan_data,
            summary=summary,
            issues=issues,
            duration_ms=duration_ms,
            commands_executed=commands_executed
        )
        
        # Generate content
        content_parts = []
        content_parts.append({
            "type": "text",
            "text": f"**Spanning Tree Audit Report: {device.host}**\n\n"
                   f"Mode: {mode_data.get('mode', 'Unknown')}\n"
                   f"Protocol: {mode_data.get('protocol', 'Unknown')}\n"
                   f"Root Bridge: {'YES' if summary['is_root_bridge'] else 'NO'}\n"
                   f"Topology Changes: {summary['topology_changes']}\n\n"
                   f"Ports - Total: {summary['total_ports']} | "
                   f"Forwarding: {summary['forwarding_ports']} | "
                   f"Blocking: {summary['blocking_ports']}\n"
                   f"VLANs - Total: {summary['total_vlans']} | "
                   f"STP Enabled: {summary['vlans_stp_enabled']} | "
                   f"STP Disabled: {summary['vlans_stp_disabled']}\n"
        })
        
        if issues:
            content_parts.append({
                "type": "text",
                "text": f"\n⚠️ Issues Detected ({len(issues)}):\n" + 
                       "\n".join(f"{i+1}. {issue}" for i, issue in enumerate(issues[:10]))
            })
            if len(issues) > 10:
                content_parts.append({
                    "type": "text",
                    "text": f"\n... and {len(issues) - 10} more issues"
                })
        
        return {
            **result.model_dump(),
            "content": content_parts
        }

    # ========================================================================
    # CONFIG BACKUP
    # ========================================================================
    if tool == "aos.config.backup":
        class ArgsConfigBackup(BaseModel):
            host: str = Field(description="Target switch IP address or hostname")
            username: Optional[str] = Field(default=None, description="SSH username (defaults to AOS_DEVICE_USERNAME env var)")
            
        args_obj = ArgsConfigBackup(**args)
        authorize_tool(ctx, cfg.authz, tool)
        
        # Create device and execute write terminal command
        device = create_device_from_host(args_obj.host, 22, args_obj.username)
        cmd = "write terminal"
        res = runner.run(device, cmd, timeout_s=60)
        
        import time
        result = {
            "host": args_obj.host,
            "config": res.stdout.strip(),
            "size_bytes": len(res.stdout),
            "duration_ms": res.duration_ms,
            "timestamp": int(time.time()),
            "commands_executed": [cmd]
        }
        
        return {
            **result,
            "content": [
                {
                    "type": "text",
                    "text": f"**Configuration Backup: {args_obj.host}**\n\nSize: {len(res.stdout)} bytes\nDuration: {res.duration_ms}ms\n"
                }
            ]
        }

    raise KeyError(f"Unknown tool: {tool}")


def tool_infos(cfg: Optional[AppConfig] = None) -> List[ToolInfo]:
    """Return list of all available tools with their metadata."""
    return [
        ToolInfo(
            name="aos.cli.readonly",
            description="Execute read-only CLI commands on Alcatel-Lucent OmniSwitch devices. Returns raw command output.",
            input_schema={
                "type": "object",
                "properties": {
                    "host": {
                        "type": "string",
                        "description": "Target switch IP address or hostname"
                    },
                    "command": {
                        "type": "string",
                        "description": "CLI command to execute (read-only only)"
                    },
                    "port": {
                        "type": "integer",
                        "description": "SSH port (default: 22)",
                        "default": 22
                    },
                    "username": {
                        "type": "string",
                        "description": "SSH username (uses AOS_DEVICE_USERNAME env var if not provided)"
                    },
                    "timeout_s": {
                        "type": "integer",
                        "description": "Command timeout in seconds"
                    }
                },
                "required": ["host", "command"]
            },
            output_schema={
                "type": "object",
                "properties": {
                    "host": {"type": "string"},
                    "command": {"type": "string"},
                    "stdout": {"type": "string"},
                    "stderr": {"type": "string"},
                    "exit_status": {"type": ["integer", "null"]},
                    "duration_ms": {"type": "integer"},
                    "truncated": {"type": "boolean"},
                    "redacted": {"type": "boolean"}
                }
            },
            required_scopes=[]
        ),
        ToolInfo(
            name="aos.autodiscover",
            description="Discover Alcatel-Lucent OmniSwitch devices on the network via SNMP. Returns list of discovered switches with basic information.",
            input_schema={
                "type": "object",
                "properties": {
                    "network": {
                        "type": "string",
                        "description": "Network range to scan (CIDR notation, e.g., 10.9.0.0/24)"
                    },
                    "community": {
                        "type": "string",
                        "description": "SNMP community string (uses AOS_SNMP_COMMUNITY env var if not provided)"
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "SNMP timeout in seconds (default: 2)",
                        "default": 2
                    },
                    "retries": {
                        "type": "integer",
                        "description": "Number of SNMP retries (default: 1)",
                        "default": 1
                    }
                },
                "required": ["network"]
            },
            output_schema={
                "type": "object",
                "properties": {
                    "network": {"type": "string"},
                    "discovered": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "ip": {"type": "string"},
                                "hostname": {"type": "string"},
                                "model": {"type": "string"},
                                "description": {"type": "string"}
                            }
                        }
                    },
                    "scan_duration_ms": {"type": "integer"}
                }
            },
            required_scopes=[]
        ),
        ToolInfo(
            name="aos.diag.poe",
            description="Get detailed Power over Ethernet (PoE) diagnostics for an OmniSwitch. Returns parsed PoE status including per-port power consumption, power classes, detection status, and chassis power budget information.",
            input_schema={
                "type": "object",
                "properties": {
                    "host": {
                        "type": "string",
                        "description": "Target switch IP address or hostname"
                    },
                    "slot": {
                        "type": "string",
                        "description": "Slot number to query (e.g., '1' for slot 1)",
                        "default": "1"
                    },
                    "port": {
                        "type": "integer",
                        "description": "SSH port (default: 22)",
                        "default": 22
                    },
                    "username": {
                        "type": "string",
                        "description": "SSH username (uses AOS_DEVICE_USERNAME env var if not provided)"
                    },
                    "include_raw": {
                        "type": "boolean",
                        "description": "Include raw command output in response (default: false)",
                        "default": False
                    }
                },
                "required": ["host"]
            },
            output_schema={
                "type": "object",
                "properties": {
                    "host": {"type": "string"},
                    "command": {"type": "string"},
                    "ports": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "port": {"type": "string"},
                                "admin": {"type": "string"},
                                "power": {"type": "string"},
                                "device": {"type": "string"},
                                "class": {"type": "string"},
                                "power_w": {"type": "number"},
                                "voltage_v": {"type": "number"},
                                "current_ma": {"type": "number"}
                            }
                        }
                    },
                    "chassis_summary": {
                        "type": "object",
                        "properties": {
                            "total_power_w": {"type": "number"},
                            "used_power_w": {"type": "number"},
                            "available_power_w": {"type": "number"}
                        }
                    },
                    "duration_ms": {"type": "integer"},
                    "raw_stdout": {"type": ["string", "null"]}
                }
            },
            required_scopes=[]
        ),
        ToolInfo(
            name="aos.poe.restart",
            description="Restart PoE on a specific port. This is useful for power cycling devices connected via PoE (phones, access points, cameras, etc.). The tool stops PoE, waits, then starts it again.",
            input_schema={
                "type": "object",
                "properties": {
                    "host": {
                        "type": "string",
                        "description": "Target switch IP address or hostname"
                    },
                    "port_id": {
                        "type": "string",
                        "description": "Port identifier in AOS format (e.g., '1/1/1' for chassis/slot/port)"
                    },
                    "wait_seconds": {
                        "type": "integer",
                        "description": "Seconds to wait between stop and start (default: 5)",
                        "default": 5
                    },
                    "port": {
                        "type": "integer",
                        "description": "SSH port (default: 22)",
                        "default": 22
                    },
                    "username": {
                        "type": "string",
                        "description": "SSH username (uses AOS_DEVICE_USERNAME env var if not provided)"
                    }
                },
                "required": ["host", "port_id"]
            },
            output_schema={
                "type": "object",
                "properties": {
                    "host": {"type": "string"},
                    "portId": {"type": "string"},
                    "waitSeconds": {"type": "integer"},
                    "stopCommand": {"type": "string"},
                    "startCommand": {"type": "string"},
                    "stopResult": {"type": "string"},
                    "startResult": {"type": "string"},
                    "success": {"type": "boolean"},
                    "durationMs": {"type": "integer"}
                }
            },
            required_scopes=[]
        ),
        ToolInfo(
            name="aos.device.facts",
            description="Retrieve detailed device facts and information from an OmniSwitch. Returns hostname, model, AOS version, serial number, uptime, and other system details. Works with both AOS6 and AOS8.",
            input_schema={
                "type": "object",
                "properties": {
                    "host": {
                        "type": "string",
                        "description": "Target switch IP address or hostname"
                    },
                    "refresh": {
                        "type": "boolean",
                        "description": "Force refresh of cached facts (default: true)",
                        "default": True
                    },
                    "port": {
                        "type": "integer",
                        "description": "SSH port (default: 22)",
                        "default": 22
                    }
                },
                "required": ["host"]
            },
            output_schema={
                "type": "object",
                "properties": {
                    "host": {"type": "string"},
                    "hostname": {"type": ["string", "null"]},
                    "model": {"type": ["string", "null"]},
                    "aos_version": {"type": ["string", "null"]},
                    "serial_number": {"type": ["string", "null"]},
                    "uptime": {"type": ["string", "null"]},
                    "mac_address": {"type": ["string", "null"]},
                    "facts": {"type": "object"},
                    "duration_ms": {"type": "integer"}
                }
            },
            required_scopes=[]
        ),
        ToolInfo(
            name="aos.port.info",
            description="Get detailed information about a specific switch port. Returns admin state, operational state, speed, duplex, VLAN, and other port details. Works with both AOS6 and AOS8.",
            input_schema={
                "type": "object",
                "properties": {
                    "host": {
                        "type": "string",
                        "description": "Target switch IP address or hostname"
                    },
                    "port_id": {
                        "type": "string",
                        "description": "Port identifier in AOS format (e.g., '1/1/1' for chassis/slot/port)"
                    },
                    "port": {
                        "type": "integer",
                        "description": "SSH port (default: 22)",
                        "default": 22
                    }
                },
                "required": ["host", "port_id"]
            },
            output_schema={
                "type": "object",
                "properties": {
                    "host": {"type": "string"},
                    "port_id": {"type": "string"},
                    "admin_state": {"type": ["string", "null"]},
                    "oper_state": {"type": ["string", "null"]},
                    "speed": {"type": ["string", "null"]},
                    "duplex": {"type": ["string", "null"]},
                    "vlan": {"type": ["string", "null"]},
                    "description": {"type": ["string", "null"]},
                    "mac_address": {"type": ["string", "null"]},
                    "mtu": {"type": ["integer", "null"]},
                    "errors": {"type": ["object", "null"]},
                    "raw_output": {"type": ["string", "null"]},
                    "duration_ms": {"type": "integer"}
                }
            },
            required_scopes=[]
        ),
        ToolInfo(
            name="aos.interfaces.discover",
            description="Comprehensive interface discovery - aggregates information from multiple sources (status, VLANs, MACs, LLDP, PoE) to provide complete view of all switch ports in a single call. Perfect for network inventory, topology mapping, and troubleshooting.",
            input_schema={
                "type": "object",
                "properties": {
                    "host": {
                        "type": "string",
                        "description": "Target switch IP address or hostname"
                    },
                    "port": {
                        "type": "integer",
                        "description": "SSH port (default: 22)",
                        "default": 22
                    },
                    "include_inactive": {
                        "type": "boolean",
                        "description": "Include inactive/down ports in results (default: true)",
                        "default": True
                    },
                    "include_statistics": {
                        "type": "boolean",
                        "description": "Include traffic statistics (slower, default: false)",
                        "default": False
                    }
                },
                "required": ["host"]
            },
            output_schema={
                "type": "object",
                "properties": {
                    "host": {"type": "string"},
                    "total_ports": {"type": "integer"},
                    "active_ports": {"type": "integer"},
                    "duration_ms": {"type": "integer"},
                    "commands_executed": {
                        "type": "array",
                        "items": {"type": "string"}
                    },
                    "ports": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "port_id": {"type": "string"},
                                "admin_state": {"type": "string"},
                                "oper_state": {"type": "string"},
                                "speed": {"type": ["string", "null"]},
                                "duplex": {"type": ["string", "null"]},
                                "auto_neg": {"type": "boolean"},
                                "description": {"type": ["string", "null"]},
                                "vlan": {
                                    "type": "object",
                                    "properties": {
                                        "untagged": {"type": ["integer", "null"]},
                                        "tagged": {"type": "array", "items": {"type": "integer"}},
                                        "status": {"type": ["string", "null"]}
                                    }
                                },
                                "mac_addresses": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "mac": {"type": "string"},
                                            "vlan": {"type": "integer"},
                                            "type": {"type": "string"}
                                        }
                                    }
                                },
                                "lldp_neighbor": {
                                    "type": ["object", "null"],
                                    "properties": {
                                        "chassis_id": {"type": "string"},
                                        "port_id": {"type": "string"},
                                        "port_description": {"type": ["string", "null"]},
                                        "system_name": {"type": ["string", "null"]},
                                        "system_description": {"type": ["string", "null"]},
                                        "management_ip": {"type": ["string", "null"]},
                                        "capabilities": {"type": ["string", "null"]}
                                    }
                                },
                                "poe": {
                                    "type": ["object", "null"],
                                    "properties": {
                                        "enabled": {"type": "boolean"},
                                        "status": {"type": "string"},
                                        "power_used_mw": {"type": "integer"},
                                        "max_power_mw": {"type": "integer"},
                                        "device_class": {"type": ["string", "null"]},
                                        "priority": {"type": "string"}
                                    }
                                }
                            }
                        }
                    }
                }
            },
            required_scopes=[]
        ),
        ToolInfo(
            name="aos.port.discover",
            description="Fast comprehensive discovery of a SINGLE port - aggregates status, VLANs, MACs, LLDP, and PoE information using port-specific commands. Much faster than aos.interfaces.discover for single port queries (~2-3s vs ~9s).",
            input_schema={
                "type": "object",
                "properties": {
                    "host": {
                        "type": "string",
                        "description": "Target switch IP address or hostname"
                    },
                    "port_id": {
                        "type": "string",
                        "description": "Port identifier (e.g., '1/1/1', '1/1/19')"
                    },
                    "port": {
                        "type": "integer",
                        "description": "SSH port (default: 22)",
                        "default": 22
                    }
                },
                "required": ["host", "port_id"]
            },
            output_schema={
                "type": "object",
                "properties": {
                    "host": {"type": "string"},
                    "duration_ms": {"type": "integer"},
                    "commands_executed": {
                        "type": "array",
                        "items": {"type": "string"}
                    },
                    "port": {
                        "type": "object",
                        "properties": {
                            "port_id": {"type": "string"},
                            "admin_state": {"type": "string"},
                            "oper_state": {"type": "string"},
                            "speed": {"type": ["string", "null"]},
                            "duplex": {"type": ["string", "null"]},
                            "auto_neg": {"type": "boolean"},
                            "description": {"type": ["string", "null"]},
                            "vlan": {
                                "type": "object",
                                "properties": {
                                    "untagged": {"type": ["integer", "null"]},
                                    "tagged": {"type": "array", "items": {"type": "integer"}},
                                    "status": {"type": ["string", "null"]}
                                }
                            },
                            "mac_addresses": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "mac": {"type": "string"},
                                        "vlan": {"type": "integer"},
                                        "type": {"type": "string"}
                                    }
                                }
                            },
                            "lldp_neighbor": {
                                "type": ["object", "null"],
                                "properties": {
                                    "chassis_id": {"type": "string"},
                                    "port_id": {"type": "string"},
                                    "port_description": {"type": ["string", "null"]},
                                    "system_name": {"type": ["string", "null"]},
                                    "system_description": {"type": ["string", "null"]},
                                    "management_ip": {"type": ["string", "null"]},
                                    "capabilities": {"type": ["string", "null"]}
                                }
                            },
                            "poe": {
                                "type": ["object", "null"],
                                "properties": {
                                    "enabled": {"type": "boolean"},
                                    "status": {"type": "string"},
                                    "power_used_mw": {"type": "integer"},
                                    "max_power_mw": {"type": "integer"},
                                    "device_class": {"type": ["string", "null"]},
                                    "priority": {"type": "string"}
                                }
                            }
                        }
                    }
                }
            },
            required_scopes=[]
        ),
        ToolInfo(
            name="aos.vlan.audit",
            description="Audit VLAN configuration on the switch - lists all VLANs with their state, detects configuration issues, and provides recommendations. Can audit all VLANs or a specific VLAN ID.",
            input_schema={
                "type": "object",
                "properties": {
                    "host": {
                        "type": "string",
                        "description": "Target switch IP address or hostname"
                    },
                    "vlan_id": {
                        "type": "integer",
                        "description": "Specific VLAN ID to audit (omit to audit all VLANs)"
                    },
                    "port": {
                        "type": "integer",
                        "description": "SSH port (default: 22)",
                        "default": 22
                    }
                },
                "required": ["host"]
            },
            output_schema={
                "type": "object",
                "properties": {
                    "host": {"type": "string"},
                    "total_vlans": {"type": "integer"},
                    "vlans": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "vlan_id": {"type": "integer"},
                                "name": {"type": "string"},
                                "type": {"type": "string"},
                                "admin_state": {"type": "string"},
                                "oper_state": {"type": "string"},
                                "ip_routing": {"type": ["string", "null"]},
                                "mtu": {"type": "integer"},
                                "mac_tunneling": {"type": ["string", "null"]}
                            }
                        }
                    },
                    "summary": {
                        "type": "object",
                        "description": "Statistics summary"
                    },
                    "issues": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Detected configuration issues"
                    },
                    "duration_ms": {"type": "integer"},
                    "commands_executed": {
                        "type": "array",
                        "items": {"type": "string"}
                    }
                }
            },
            required_scopes=[]
        ),
        ToolInfo(
            name="aos.routing.audit",
            description="Audit routing configuration on an OmniSwitch. Analyzes VRFs, OSPF configuration, neighbors, and routing table. Detects configuration issues like down interfaces or OSPF neighbor problems.",
            input_schema={
                "type": "object",
                "properties": {
                    "host": {
                        "type": "string",
                        "description": "Target switch IP address or hostname"
                    },
                    "port": {
                        "type": "integer",
                        "description": "SSH port (default: 22)",
                        "default": 22
                    },
                    "include_routes": {
                        "type": "boolean",
                        "description": "Include routing table sample (default: false)",
                        "default": False
                    },
                    "route_limit": {
                        "type": "integer",
                        "description": "Maximum routes to return if include_routes is true (default: 100)",
                        "default": 100
                    },
                    "protocol_filter": {
                        "type": "string",
                        "description": "Filter routes by protocol: 'OSPF', 'STATIC', 'LOCAL', 'BGP', etc. (optional)",
                        "default": None
                    }
                },
                "required": ["host"]
            },
            output_schema={
                "type": "object",
                "properties": {
                    "host": {"type": "string"},
                    "vrfs": {
                        "type": "array",
                        "items": {"type": "object"},
                        "description": "VRF configurations with OSPF and IP interface details"
                    },
                    "total_routes": {
                        "type": "integer",
                        "description": "Total number of routes"
                    },
                    "routes": {
                        "type": ["array", "null"],
                        "items": {"type": "object"},
                        "description": "Sample routes if requested"
                    },
                    "summary": {
                        "type": "object",
                        "description": "Summary statistics"
                    },
                    "issues": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Detected routing issues"
                    },
                    "duration_ms": {"type": "integer"},
                    "commands_executed": {
                        "type": "array",
                        "items": {"type": "string"}
                    }
                }
            },
            required_scopes=[]
        ),
        ToolInfo(
            name="aos.spantree.audit",
            description="Audit Spanning Tree Protocol (STP/RSTP/MSTP) configuration on an OmniSwitch. Analyzes STP mode, CIST, port states, and per-VLAN STP status. Detects issues like disabled STP, non-forwarding ports, and topology problems.",
            input_schema={
                "type": "object",
                "properties": {
                    "host": {
                        "type": "string",
                        "description": "Target switch IP address or hostname"
                    },
                    "port": {
                        "type": "integer",
                        "description": "SSH port (default: 22)",
                        "default": 22
                    }
                },
                "required": ["host"]
            },
            output_schema={
                "type": "object",
                "properties": {
                    "host": {"type": "string"},
                    "mode": {
                        "type": "object",
                        "description": "STP mode configuration"
                    },
                    "cist": {
                        "type": "object",
                        "description": "Common and Internal Spanning Tree information"
                    },
                    "ports": {
                        "type": "array",
                        "items": {"type": "object"},
                        "description": "Per-port STP status"
                    },
                    "vlans": {
                        "type": "array",
                        "items": {"type": "object"},
                        "description": "Per-VLAN STP status"
                    },
                    "summary": {
                        "type": "object",
                        "description": "Summary statistics"
                    },
                    "issues": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Detected STP issues"
                    },
                    "duration_ms": {"type": "integer"},
                    "commands_executed": {
                        "type": "array",
                        "items": {"type": "string"}
                    }
                }
            },
            required_scopes=[]
        ),
        ToolInfo(
            name="aos.config.backup",
            description="Backup the complete running configuration of an OmniSwitch using 'write terminal'. Returns the full configuration as text for backup/archival purposes.",
            input_schema={
                "type": "object",
                "properties": {
                    "host": {
                        "type": "string",
                        "description": "Target switch IP address or hostname"
                    }
                },
                "required": ["host"]
            },
            output_schema={
                "type": "object",
                "properties": {
                    "host": {"type": "string"},
                    "config": {
                        "type": "string",
                        "description": "Full running configuration text"
                    },
                    "size_bytes": {
                        "type": "integer",
                        "description": "Configuration size in bytes"
                    },
                    "timestamp": {"type": "number"},
                    "duration_ms": {"type": "integer"},
                    "commands_executed": {
                        "type": "array",
                        "items": {"type": "string"}
                    }
                }
            },
            required_scopes=[]
        ),
    ]
