"""Network tools - MAC lookup, LACP, NTP status, DHCP relay.

Tools: aos.mac.lookup, aos.lacp.info, aos.ntp.status, aos.dhcp.relay.info
"""

import re
import time
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from .base import create_device_from_host
from ..policy import compile_policy, sanitize_command
from ..config import AppConfig
from ..ssh_runner import SSHRunner
from ..lacp_parse import parse_show_linkagg, parse_show_lacp, analyze_lacp_issues
from ..ntp_parse import (
    parse_show_ntp_status, parse_show_ntp_client_server_list, analyze_ntp_status
)
from ..dhcp_parse import (
    parse_show_dhcp_relay_interface, parse_show_dhcp_relay_counters, analyze_dhcp_relay
)


# =============================================================================
# MODELS
# =============================================================================

class ArgsMacLookup(BaseModel):
    host: str = Field(description="Target switch IP address")
    mac_address: Optional[str] = Field(default=None, description="MAC address to lookup")
    ip_address: Optional[str] = Field(default=None, description="IP address to find MAC via ARP")
    vlan_id: Optional[int] = Field(default=None, description="Filter by VLAN")
    port: Optional[int] = Field(default=22)


class ArgsLacpInfo(BaseModel):
    host: str = Field(description="Target switch IP address")
    port: Optional[int] = Field(default=22)


class ArgsNtpStatus(BaseModel):
    host: str = Field(description="Target switch IP address")
    include_servers: bool = Field(default=True, description="Include NTP server list")
    port: Optional[int] = Field(default=22)


class ArgsDhcpRelayInfo(BaseModel):
    host: str = Field(description="Target switch IP address")
    vlan_id: Optional[int] = Field(default=None, description="Specific VLAN")
    port: Optional[int] = Field(default=22)


# =============================================================================
# HANDLERS
# =============================================================================

def handle_mac_lookup(
    cfg: AppConfig,
    runner: SSHRunner,
    args: Dict[str, Any],
    zone_resolver: Any = None,
) -> Dict[str, Any]:
    """Lookup MAC address or find MAC from IP via ARP."""
    parsed = ArgsMacLookup.model_validate(args)
    device = create_device_from_host(parsed.host, parsed.port or 22)
    compiled_policy = compile_policy(cfg.command_policy)
    
    start_time = time.time()
    commands_executed = []
    entries = []
    
    # Lookup by MAC address
    if parsed.mac_address:
        mac = parsed.mac_address.replace("-", ":").lower()
        cmd = f"show mac-learning mac {mac}"
        safe_cmd = sanitize_command(cmd, compiled_policy)
        res = runner.run(device, safe_cmd, timeout_s=10, zone_resolver=zone_resolver)
        commands_executed.append(cmd)
        
        # Parse MAC learning output
        for line in res.stdout.split('\n'):
            # OS6860 format: "VLAN    1098   70:4c:a5:50:45:ce    dynamic     bridging      1/1/24"
            match = re.search(r'VLAN\s+(\d+)\s+([0-9a-fA-F:]{17})\s+(dynamic|static)\s+\w+\s+(\S+)', line, re.IGNORECASE)
            if match:
                vlan, mac_addr, mac_type, port = match.groups()
                entries.append({
                    "mac_address": mac_addr, "vlan": int(vlan),
                    "port": port, "type": mac_type.lower()
                })
                continue
            
            # Standard format: "MAC Address   VLAN   Port   Type"
            std_match = re.search(r'([0-9a-fA-F:]{17})\s+(\d+)\s+(\S+)\s+(dynamic|static)', line, re.IGNORECASE)
            if std_match:
                mac_addr, vlan, port, mac_type = std_match.groups()
                entries.append({
                    "mac_address": mac_addr, "vlan": int(vlan),
                    "port": port, "type": mac_type.lower()
                })
    
    # Lookup by IP address (via ARP)
    if parsed.ip_address:
        cmd = f"show arp {parsed.ip_address}"
        safe_cmd = sanitize_command(cmd, compiled_policy)
        res = runner.run(device, safe_cmd, timeout_s=10, zone_resolver=zone_resolver)
        commands_executed.append(cmd)
        
        for line in res.stdout.split('\n'):
            match = re.search(r'(\d+\.\d+\.\d+\.\d+)\s+([0-9a-fA-F:]{17})\s+(\d+)\s+(\S+)', line)
            if match:
                ip_addr, mac_addr, vlan, port = match.groups()
                entries.append({
                    "ip_address": ip_addr, "mac_address": mac_addr,
                    "vlan": int(vlan), "port": port, "type": "arp"
                })
    
    # Lookup by VLAN only or all MACs
    if parsed.vlan_id and not parsed.mac_address and not parsed.ip_address:
        # Try specific VLAN first, fall back to domain vlan (filter locally)
        cmd = "show mac-learning domain vlan"
        safe_cmd = sanitize_command(cmd, compiled_policy)
        res = runner.run(device, safe_cmd, timeout_s=15, zone_resolver=zone_resolver)
        commands_executed.append(cmd)
        
        for line in res.stdout.split('\n'):
            # OS6860 format: "VLAN    78   ac:71:2e:98:1f:3c    dynamic     bridging     1/1/1"
            match = re.search(r'VLAN\s+(\d+)\s+([0-9a-fA-F:]{17})\s+(dynamic|static)\s+\w+\s+(\S+)', line, re.IGNORECASE)
            if match:
                vlan, mac_addr, mac_type, port = match.groups()
                # Filter by requested VLAN
                if int(vlan) == parsed.vlan_id:
                    entries.append({
                        "mac_address": mac_addr, "vlan": int(vlan),
                        "port": port, "type": mac_type.lower()
                    })
                continue
            std_match = re.search(r'([0-9a-fA-F:]{17})\s+(\d+)\s+(\S+)\s+(dynamic|static)', line, re.IGNORECASE)
            if std_match:
                mac_addr, vlan, port, mac_type = std_match.groups()
                if int(vlan) == parsed.vlan_id:
                    entries.append({
                        "mac_address": mac_addr, "vlan": int(vlan),
                        "port": port, "type": mac_type.lower()
                    })
    
    # If no filter specified, get all MACs (limited)
    if not parsed.mac_address and not parsed.ip_address and not parsed.vlan_id:
        cmd = "show mac-learning domain vlan"
        safe_cmd = sanitize_command(cmd, compiled_policy)
        res = runner.run(device, safe_cmd, timeout_s=15, zone_resolver=zone_resolver)
        commands_executed.append(cmd)
        
        for line in res.stdout.split('\n'):
            if len(entries) >= 100:  # Limit for LLM
                break
            match = re.search(r'VLAN\s+(\d+)\s+([0-9a-fA-F:]{17})\s+(dynamic|static)\s+\w+\s+(\S+)', line, re.IGNORECASE)
            if match:
                vlan, mac_addr, mac_type, port = match.groups()
                entries.append({
                    "mac_address": mac_addr, "vlan": int(vlan),
                    "port": port, "type": mac_type.lower()
                })
    
    duration_ms = int((time.time() - start_time) * 1000)
    
    # Build content
    if entries:
        content_text = f"**MAC Lookup Results: {device.host}**\n\nFound: {len(entries)} entries\n"
        for entry in entries[:10]:
            content_text += f"\n- MAC: {entry.get('mac_address', 'N/A')}"
            if 'ip_address' in entry:
                content_text += f" | IP: {entry['ip_address']}"
            content_text += f" | VLAN: {entry.get('vlan', 'N/A')} | Port: {entry.get('port', 'N/A')}"
    else:
        content_text = f"**MAC Lookup: {device.host}**\n\nNo entries found."
    
    return {
        "host": device.host,
        "entries": entries,
        "total_found": len(entries),
        "duration_ms": duration_ms,
        "commands_executed": commands_executed,
        "content": [{"type": "text", "text": content_text}]
    }


def handle_lacp_info(
    cfg: AppConfig,
    runner: SSHRunner,
    args: Dict[str, Any],
    zone_resolver: Any = None,
) -> Dict[str, Any]:
    """Get LACP/Link Aggregation information."""
    parsed = ArgsLacpInfo.model_validate(args)
    device = create_device_from_host(parsed.host, parsed.port or 22)
    compiled_policy = compile_policy(cfg.command_policy)
    
    start_time = time.time()
    commands_executed = []
    
    # Execute link aggregation commands
    linkagg_cmd = "show linkagg"
    safe_cmd = sanitize_command(linkagg_cmd, compiled_policy)
    linkagg_result = runner.run(device, safe_cmd, timeout_s=15, zone_resolver=zone_resolver)
    commands_executed.append(linkagg_cmd)
    linkagg_data = parse_show_linkagg(linkagg_result.stdout)
    
    # Try LACP protocol info
    lacp_data = {"lacp_enabled": False, "aggregates": []}
    try:
        lacp_cmd = "show lacp"
        safe_lacp = sanitize_command(lacp_cmd, compiled_policy)
        lacp_result = runner.run(device, safe_lacp, timeout_s=10, zone_resolver=zone_resolver)
        commands_executed.append(lacp_cmd)
        lacp_data = parse_show_lacp(lacp_result.stdout)
    except Exception:
        pass
    
    # Analyze issues
    issues = analyze_lacp_issues(lacp_data, linkagg_data)
    issues.extend(linkagg_data.get("issues", []))
    
    duration_ms = int((time.time() - start_time) * 1000)
    lags = linkagg_data.get("lags", [])
    total_lags = linkagg_data.get("total_lags", 0)
    lacp_enabled = lacp_data.get("lacp_enabled", False)
    
    # Build content
    status_emoji = "✅" if not issues else "⚠️"
    content_text = (
        f"{status_emoji} **LACP/Link Aggregation: {device.host}**\n\n"
        f"Total LAGs: {total_lags}\n"
        f"LACP Protocol: {'Enabled' if lacp_enabled else 'Disabled'}\n"
    )
    
    if lags:
        lags_up = len([lag for lag in lags if lag.get("oper_state") == "up"])
        content_text += f"Operational LAGs: {lags_up}/{total_lags}\n"
        for lag in lags[:10]:
            content_text += (
                f"\n- LAG {lag['agg_id']} ({lag.get('name', 'unnamed')}): "
                f"{lag.get('oper_state', 'unknown').upper()} - {lag.get('size', 0)} members"
            )
    
    if issues:
        content_text += f"\n\n⚠️ Issues ({len(issues)}):\n" + "\n".join(f"- {i}" for i in issues[:10])
    
    return {
        "host": device.host,
        "lags": lags,
        "total_lags": total_lags,
        "lacp_enabled": lacp_enabled,
        "issues": issues,
        "duration_ms": duration_ms,
        "commands_executed": commands_executed,
        "content": [{"type": "text", "text": content_text}]
    }


def handle_ntp_status(
    cfg: AppConfig,
    runner: SSHRunner,
    args: Dict[str, Any],
    zone_resolver: Any = None,
) -> Dict[str, Any]:
    """Get NTP synchronization status."""
    parsed = ArgsNtpStatus.model_validate(args)
    device = create_device_from_host(parsed.host, parsed.port or 22)
    compiled_policy = compile_policy(cfg.command_policy)
    
    start_time = time.time()
    commands_executed = []
    
    # Get NTP status
    ntp_cmd = "show ntp status"
    safe_cmd = sanitize_command(ntp_cmd, compiled_policy)
    ntp_result = runner.run(device, safe_cmd, timeout_s=10, zone_resolver=zone_resolver)
    commands_executed.append(ntp_cmd)
    ntp_status = parse_show_ntp_status(ntp_result.stdout)
    
    # Get server list if requested
    servers = []
    if parsed.include_servers:
        try:
            srv_cmd = "show ntp client server-list"
            safe_srv = sanitize_command(srv_cmd, compiled_policy)
            srv_result = runner.run(device, safe_srv, timeout_s=10, zone_resolver=zone_resolver)
            commands_executed.append(srv_cmd)
            servers = parse_show_ntp_client_server_list(srv_result.stdout)
        except Exception:
            pass
    
    issues = analyze_ntp_status(ntp_status, servers)
    duration_ms = int((time.time() - start_time) * 1000)
    
    synchronized = ntp_status.get("synchronized", False)
    mode = ntp_status.get("mode", "unknown")
    stratum = ntp_status.get("stratum")
    reference_clock = ntp_status.get("reference_clock")
    offset_ms = ntp_status.get("offset_ms")
    
    # Build content
    status_emoji = "✅" if synchronized else "❌"
    content_text = (
        f"{status_emoji} **NTP Status: {device.host}**\n\n"
        f"Synchronized: {'Yes' if synchronized else 'No'}\n"
        f"Mode: {mode}\n"
        f"Stratum: {stratum or 'Unknown'}\n"
        f"Reference: {reference_clock or 'None'}\n"
    )
    
    if offset_ms is not None:
        content_text += f"Offset: {offset_ms:.2f}ms\n"
    
    if servers:
        content_text += f"\nConfigured Servers: {len(servers)}"
    
    if issues:
        content_text += f"\n\n⚠️ Issues ({len(issues)}):\n" + "\n".join(f"- {i}" for i in issues[:10])
    
    return {
        "host": device.host,
        "synchronized": synchronized,
        "mode": mode,
        "stratum": stratum,
        "reference_clock": reference_clock,
        "offset_ms": offset_ms,
        "servers": servers,
        "issues": issues,
        "duration_ms": duration_ms,
        "commands_executed": commands_executed,
        "content": [{"type": "text", "text": content_text}]
    }


def handle_dhcp_relay_info(
    cfg: AppConfig,
    runner: SSHRunner,
    args: Dict[str, Any],
    zone_resolver: Any = None,
) -> Dict[str, Any]:
    """Get DHCP relay configuration and counters."""
    parsed = ArgsDhcpRelayInfo.model_validate(args)
    device = create_device_from_host(parsed.host, parsed.port or 22)
    compiled_policy = compile_policy(cfg.command_policy)
    
    start_time = time.time()
    commands_executed = []
    
    # Get DHCP relay config (show ip dhcp-relay interface)
    relay_cmd = "show ip dhcp-relay interface"
    safe_cmd = sanitize_command(relay_cmd, compiled_policy)
    relay_result = runner.run(device, safe_cmd, timeout_s=10, zone_resolver=zone_resolver)
    commands_executed.append(relay_cmd)
    relay_config = parse_show_dhcp_relay_interface(relay_result.stdout)
    
    # Get counters (show ip dhcp-relay counters)
    counters = {}
    try:
        counters_cmd = "show ip dhcp-relay counters"
        safe_counters = sanitize_command(counters_cmd, compiled_policy)
        counters_result = runner.run(device, safe_counters, timeout_s=10, zone_resolver=zone_resolver)
        commands_executed.append(counters_cmd)
        counters = parse_show_dhcp_relay_counters(counters_result.stdout)
    except Exception:
        pass
    
    issues = analyze_dhcp_relay(relay_config, counters)
    duration_ms = int((time.time() - start_time) * 1000)
    
    # Extract data from relay_config (now a dict)
    enabled = relay_config.get("admin_status") == "enabled"
    interfaces = relay_config.get("interfaces", [])
    
    # Build content
    status_emoji = "✅" if enabled and not issues else "⚠️" if issues else "ℹ️"
    content_text = (
        f"{status_emoji} **DHCP Relay: {device.host}**\n\n"
        f"Status: {'Enabled' if enabled else 'Disabled'}\n"
        f"Mode: {relay_config.get('relay_mode', 'N/A')}\n"
        f"Interfaces: {len(interfaces)}\n"
    )
    
    if interfaces:
        for intf in interfaces[:5]:
            servers = ", ".join(intf.get('servers', []))
            content_text += f"\n- {intf.get('interface', 'N/A')}: {servers}"
    
    if counters:
        total_req = counters.get('total_client_requests', 0)
        total_resp = counters.get('total_server_responses', 0)
        content_text += f"\n\nClient Requests: {total_req:,} | Server Responses: {total_resp:,}"
    
    if issues:
        content_text += f"\n\n⚠️ Issues ({len(issues)}):\n" + "\n".join(f"- {i}" for i in issues[:5])
    
    return {
        "host": device.host,
        "enabled": enabled,
        "admin_status": relay_config.get("admin_status"),
        "relay_mode": relay_config.get("relay_mode"),
        "agent_information": relay_config.get("agent_information"),
        "pxe_support": relay_config.get("pxe_support"),
        "interfaces": interfaces,
        "counters": counters,
        "issues": issues,
        "duration_ms": duration_ms,
        "commands_executed": commands_executed,
        "content": [{"type": "text", "text": content_text}]
    }


class ArgsLldpNeighbors(BaseModel):
    host: str = Field(description="Target switch IP address")
    port_filter: Optional[str] = Field(default=None, description="Filter by port (e.g. '1/1/19')")
    port: Optional[int] = Field(default=22)


def handle_lldp_neighbors(
    cfg: AppConfig,
    runner: SSHRunner,
    args: Dict[str, Any],
    zone_resolver: Any = None,
) -> Dict[str, Any]:
    """Get LLDP neighbors - useful for finding connected devices like Ruckus APs, IP phones, etc."""
    parsed = ArgsLldpNeighbors.model_validate(args)
    device = create_device_from_host(parsed.host, parsed.port or 22)
    compiled_policy = compile_policy(cfg.command_policy)
    
    start_time = time.time()
    
    # AOS command for LLDP remote systems
    cmd = "show lldp remote-system"
    safe_cmd = sanitize_command(cmd, compiled_policy)
    result = runner.run(device, safe_cmd, timeout_s=15, zone_resolver=zone_resolver)
    
    # Parse LLDP neighbors from AOS format
    # Format is in sections like:
    # Remote LLDP nearest-bridge Agents on Local Port 1/1/19:
    #     Chassis c8:84:8c:22:b3:50, Port c8:84:8c:22:b3:50:
    #       System Name = RCK-POC-R1
    #       System Description = Ruckus R350...
    neighbors = []
    current_neighbor = None
    
    for line in result.stdout.split('\n'):
        # Match "Remote LLDP ... on Local Port X/X/X:"
        port_match = re.search(r'Local Port (\d+/\d+/\d+)', line)
        if port_match:
            if current_neighbor:
                neighbors.append(current_neighbor)
            current_neighbor = {
                "local_port": port_match.group(1),
                "remote_chassis_id": None,
                "system_name": None,
                "system_description": None,
                "management_ip": None,
                "capabilities": None,
            }
            # Try to get chassis from same line or next
            chassis_match = re.search(r'Chassis ([0-9a-f:]{17})', line, re.IGNORECASE)
            if chassis_match:
                current_neighbor["remote_chassis_id"] = chassis_match.group(1)
            continue
        
        if current_neighbor:
            # Extract chassis ID from "Chassis X:X:X:X:X:X, Port..."
            chassis_match = re.search(r'Chassis ([0-9a-f:]{17})', line, re.IGNORECASE)
            if chassis_match:
                current_neighbor["remote_chassis_id"] = chassis_match.group(1)
            
            # Extract System Name
            name_match = re.search(r'System Name\s*=\s*(.+)', line)
            if name_match:
                current_neighbor["system_name"] = name_match.group(1).strip().rstrip(',')
            
            # Extract System Description
            desc_match = re.search(r'System Description\s*=\s*(.+)', line)
            if desc_match:
                current_neighbor["system_description"] = desc_match.group(1).strip()[:100]  # Truncate
            
            # Extract Management IP
            ip_match = re.search(r'Management IP Address\s*=\s*(\d+\.\d+\.\d+\.\d+)', line)
            if ip_match:
                current_neighbor["management_ip"] = ip_match.group(1)
            
            # Extract Capabilities
            cap_match = re.search(r'Capabilities Enabled\s*=\s*(.+)', line)
            if cap_match:
                current_neighbor["capabilities"] = cap_match.group(1).strip().rstrip(',')
    
    # Don't forget the last neighbor
    if current_neighbor:
        neighbors.append(current_neighbor)
    
    # Apply port filter if specified
    if parsed.port_filter:
        neighbors = [n for n in neighbors if n.get("local_port") == parsed.port_filter]
    
    duration_ms = int((time.time() - start_time) * 1000)
    
    # Build content for LLM
    content_text = f"**LLDP Neighbors: {device.host}**\n\n"
    content_text += f"Total neighbors: {len(neighbors)}\n\n"
    
    for n in neighbors[:20]:  # Limit to 20 for readability
        content_text += f"- **Port {n.get('local_port', 'N/A')}**: "
        if n.get('system_name'):
            content_text += f"{n['system_name']}"
        if n.get('system_description'):
            content_text += f" ({n['system_description'][:50]}...)"
        if n.get('management_ip'):
            content_text += f" IP: {n['management_ip']}"
        if n.get('remote_chassis_id'):
            content_text += f" MAC: {n['remote_chassis_id']}"
        content_text += "\n"
    
    return {
        "host": device.host,
        "neighbors": neighbors,
        "total_count": len(neighbors),
        "duration_ms": duration_ms,
        "raw_output": result.stdout,
        "content": [{"type": "text", "text": content_text}]
    }


# =============================================================================
# TOOL INFO
# =============================================================================

TOOLS_INFO = [
    {
        "name": "aos.mac.lookup",
        "description": "Find where a device is connected by MAC or IP address. "
                       "Use when: locating a device on the network, finding which port a MAC is on, resolving IP to MAC via ARP. "
                       "Returns: mac_entries[] with mac_address/vlan_id/port/type, arp_entries[] if IP provided. "
                       "Combine with: aos.lldp.neighbors to identify the device type, aos.port.discover for full port details.",
        "input_schema": {
            "type": "object",
            "properties": {
                "host": {"type": "string", "description": "Switch IP address"},
                "mac_address": {"type": "string", "description": "MAC address to lookup (optional)"},
                "ip_address": {"type": "string", "description": "IP address to find MAC via ARP (optional)"},
                "vlan_id": {"type": "integer", "description": "Filter by VLAN (optional)"},
            },
            "required": ["host"]
        },
        "output_schema": {"type": "object"}
    },
    {
        "name": "aos.lacp.info",
        "description": "Get Link Aggregation (LAG/LACP) configuration and status. "
                       "Use when: checking trunk status, verifying LAG member ports, troubleshooting bonding issues. "
                       "Returns: aggregates[] with agg_id, admin_state, oper_state, member_ports[], actor_key. "
                       "For uplink troubleshooting, check member port states.",
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
        "name": "aos.ntp.status",
        "description": "Check NTP time synchronization status. "
                       "Use when: verifying clock sync, checking NTP server reachability, troubleshooting time-related issues. "
                       "Returns: mode (client/server), sync_status, reference_server, stratum, offset_ms, servers[] list. "
                       "Important for: log correlation, certificate validation, scheduled tasks.",
        "input_schema": {
            "type": "object",
            "properties": {
                "host": {"type": "string", "description": "Switch IP address"},
                "include_servers": {"type": "boolean", "description": "Include server list", "default": True},
            },
            "required": ["host"]
        },
        "output_schema": {"type": "object"}
    },
    {
        "name": "aos.dhcp.relay.info",
        "description": "Get DHCP relay configuration and packet statistics. "
                       "Use when: troubleshooting DHCP issues, verifying relay is configured, checking DHCP server connectivity. "
                       "Returns: admin_status, interfaces[] with vlan/server_ip, counters with discover/offer/request/ack counts. "
                       "Check counters to see if DHCP packets are flowing.",
        "input_schema": {
            "type": "object",
            "properties": {
                "host": {"type": "string", "description": "Switch IP address"},
                "vlan_id": {"type": "integer", "description": "Specific VLAN (optional)"},
            },
            "required": ["host"]
        },
        "output_schema": {"type": "object"}
    },
    {
        "name": "aos.lldp.neighbors",
        "description": "Discover devices connected to switch ports via LLDP protocol. "
                       "Use when: finding what's connected (APs, phones, switches), building topology maps, inventorying connected devices. "
                       "Returns: neighbors[] with local_port, remote_system_name, remote_port, remote_chassis_id, capabilities. "
                       "Best for: 'What devices are connected?' 'Find all access points' 'Show network topology'.",
        "input_schema": {
            "type": "object",
            "properties": {
                "host": {"type": "string", "description": "Switch IP address"},
                "port_filter": {"type": "string", "description": "Filter by specific port (e.g. '1/1/19')"},
            },
            "required": ["host"]
        },
        "output_schema": {"type": "object"}
    },
]
