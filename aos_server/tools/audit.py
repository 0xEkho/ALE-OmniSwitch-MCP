"""Audit tools - VLAN, Routing, and Spanning Tree audits.

Tools: aos.vlan.audit, aos.routing.audit, aos.spantree.audit
"""

import time
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from .base import create_device_from_host
from ..policy import compile_policy, sanitize_command
from ..config import AppConfig
from ..ssh_runner import SSHRunner
from ..vlan_parse import parse_show_vlan, parse_show_vlan_detail, analyze_vlan_config
from ..routing_parse import (
    parse_show_vrf, parse_show_ip_routes, parse_show_ip_ospf_interface,
    parse_show_ip_ospf_neighbor, parse_show_ip_interface
)
from ..stp_parse import (
    parse_show_spantree_mode, parse_show_spantree_cist,
    parse_show_spantree_ports, parse_show_spantree_vlan
)


# =============================================================================
# MODELS
# =============================================================================

class ArgsVlanAudit(BaseModel):
    host: str = Field(description="Target switch IP address")
    vlan_id: Optional[int] = Field(default=None, description="Specific VLAN to audit")
    port: Optional[int] = Field(default=22)


class ArgsRoutingAudit(BaseModel):
    host: str = Field(description="Target switch IP address")
    vrf: Optional[str] = Field(default=None, description="Specific VRF to audit")
    port: Optional[int] = Field(default=22)


class ArgsSpantreeAudit(BaseModel):
    host: str = Field(description="Target switch IP address")
    port: Optional[int] = Field(default=22)


# =============================================================================
# HANDLERS
# =============================================================================

def handle_vlan_audit(
    cfg: AppConfig,
    runner: SSHRunner,
    args: Dict[str, Any],
    zone_resolver: Any = None,
) -> Dict[str, Any]:
    """Audit VLAN configuration."""
    parsed = ArgsVlanAudit.model_validate(args)
    device = create_device_from_host(parsed.host, parsed.port or 22)
    compiled_policy = compile_policy(cfg.command_policy)
    
    start_time = time.time()
    commands_executed = []
    
    # Run commands
    if parsed.vlan_id:
        commands = ["show vlan", f"show vlan {parsed.vlan_id}"]
    else:
        commands = ["show vlan"]
    
    results = {}
    for cmd in commands:
        safe_cmd = sanitize_command(cmd, compiled_policy)
        res = runner.run(device, safe_cmd, timeout_s=15, zone_resolver=zone_resolver)
        results[cmd] = res.stdout
        commands_executed.append(cmd)
    
    # Parse VLANs
    vlans = parse_show_vlan(results.get("show vlan", ""))
    
    # Filter if specific VLAN
    if parsed.vlan_id:
        vlans = [v for v in vlans if v['vlan_id'] == parsed.vlan_id]
    
    # Analyze
    summary, issues = analyze_vlan_config(vlans)
    duration_ms = int((time.time() - start_time) * 1000)
    
    # Build content
    if parsed.vlan_id and vlans:
        v = vlans[0]
        content_text = (
            f"**VLAN {v['vlan_id']}: {v.get('name', 'N/A')}**\n\n"
            f"Type: {v.get('type', 'N/A')}\n"
            f"Admin: {v.get('admin_state', 'N/A')} | Oper: {v.get('oper_state', 'N/A')}\n"
            f"MTU: {v.get('mtu', 1500)}"
        )
    else:
        content_text = (
            f"**VLAN Audit: {device.host}**\n\n"
            f"Total VLANs: {summary['total']}\n"
            f"Enabled: {summary['enabled']} | Disabled: {summary['disabled']}\n"
            f"Operational: {summary['operational']}"
        )
    
    if issues:
        content_text += f"\n\n⚠️ Issues ({len(issues)}):\n" + "\n".join(f"- {i}" for i in issues[:5])
    
    return {
        "host": device.host,
        "total_vlans": len(vlans),
        "vlans": vlans,
        "summary": summary,
        "issues": issues,
        "duration_ms": duration_ms,
        "commands_executed": commands_executed,
        "content": [{"type": "text", "text": content_text}]
    }


def handle_routing_audit(
    cfg: AppConfig,
    runner: SSHRunner,
    args: Dict[str, Any],
    zone_resolver: Any = None,
) -> Dict[str, Any]:
    """Audit routing configuration (VRFs, OSPF, static routes)."""
    parsed = ArgsRoutingAudit.model_validate(args)
    device = create_device_from_host(parsed.host, parsed.port or 22)
    compiled_policy = compile_policy(cfg.command_policy)
    
    start_time = time.time()
    commands_executed = []
    
    # Commands to run
    commands = [
        "show vrf",
        "show ip routes",
        "show ip ospf interface",
        "show ip ospf neighbor",
    ]
    
    if parsed.vrf:
        commands = [
            f"vrf {parsed.vrf} show ip routes",
            f"vrf {parsed.vrf} show ip ospf interface",
            f"vrf {parsed.vrf} show ip ospf neighbor",
        ]
    
    results = {}
    for cmd in commands:
        safe_cmd = sanitize_command(cmd, compiled_policy)
        try:
            res = runner.run(device, safe_cmd, timeout_s=15, zone_resolver=zone_resolver)
            results[cmd] = res.stdout
            commands_executed.append(cmd)
        except Exception:
            pass
    
    # Parse results
    vrfs = []
    if "show vrf" in results:
        vrfs = parse_show_vrf(results["show vrf"])
    
    routes = []
    route_total = 0
    for cmd, output in results.items():
        if "routes" in cmd:
            route_data = parse_show_ip_routes(output, limit=100)  # Limit for LLM
            routes.extend(route_data.get("routes", []))
            route_total += route_data.get("total_routes", 0)
    
    ospf_neighbors = []
    for cmd, output in results.items():
        if "ospf neighbor" in cmd:
            ospf_neighbors.extend(parse_show_ip_ospf_neighbor(output))
    
    duration_ms = int((time.time() - start_time) * 1000)
    
    # Detect issues
    issues = []
    for neighbor in ospf_neighbors:
        if neighbor.get('state', '').lower() not in ['full', 'two-way']:
            issues.append(f"OSPF neighbor {neighbor.get('neighbor_id')} in state {neighbor.get('state')}")
    
    routes_shown = len(routes)
    content_text = (
        f"**Routing Audit: {device.host}**\n\n"
        f"VRFs: {len(vrfs)}\n"
        f"Routes: {route_total} total ({routes_shown} shown)\n"
        f"OSPF Neighbors: {len(ospf_neighbors)}"
    )
    
    if issues:
        content_text += f"\n\n⚠️ Issues ({len(issues)}):\n" + "\n".join(f"- {i}" for i in issues[:5])
    
    return {
        "host": device.host,
        "vrfs": vrfs,
        "routes": routes,
        "route_total": route_total,
        "ospf_neighbors": ospf_neighbors,
        "issues": issues,
        "duration_ms": duration_ms,
        "commands_executed": commands_executed,
        "content": [{"type": "text", "text": content_text}]
    }


def handle_spantree_audit(
    cfg: AppConfig,
    runner: SSHRunner,
    args: Dict[str, Any],
    zone_resolver: Any = None,
) -> Dict[str, Any]:
    """Audit Spanning Tree configuration."""
    parsed = ArgsSpantreeAudit.model_validate(args)
    device = create_device_from_host(parsed.host, parsed.port or 22)
    compiled_policy = compile_policy(cfg.command_policy)
    
    start_time = time.time()
    commands_executed = []
    
    commands = [
        "show spantree mode",
        "show spantree cist",
        "show spantree cist ports",
    ]
    
    results = {}
    for cmd in commands:
        safe_cmd = sanitize_command(cmd, compiled_policy)
        try:
            res = runner.run(device, safe_cmd, timeout_s=15, zone_resolver=zone_resolver)
            results[cmd] = res.stdout
            commands_executed.append(cmd)
        except Exception:
            pass
    
    # Parse results
    mode = parse_show_spantree_mode(results.get("show spantree mode", ""))
    cist = parse_show_spantree_cist(results.get("show spantree cist", ""))
    ports = parse_show_spantree_ports(results.get("show spantree cist ports", ""))
    
    duration_ms = int((time.time() - start_time) * 1000)
    
    # Detect issues
    issues = []
    if mode.get('status', '').lower() == 'disabled':
        issues.append("Spanning Tree is DISABLED - potential loop risk")
    
    for port in ports:
        state = port.get('state', '').lower()
        if state in ['blocking', 'listening', 'learning']:
            issues.append(f"Port {port.get('port')} in {state} state")
    
    content_text = (
        f"**Spanning Tree Audit: {device.host}**\n\n"
        f"Mode: {mode.get('mode', 'N/A')}\n"
        f"Status: {cist.get('stp_status', 'N/A')}\n"
        f"Ports monitored: {len(ports)}"
    )
    
    if cist.get('designated_root') or cist.get('cst_designated_root'):
        root = cist.get('designated_root') or cist.get('cst_designated_root')
        content_text += f"\nRoot Bridge: {root}"
    
    if issues:
        content_text += f"\n\n⚠️ Issues ({len(issues)}):\n" + "\n".join(f"- {i}" for i in issues[:5])
    
    return {
        "host": device.host,
        "mode": mode,
        "cist": cist,
        "ports": ports,
        "issues": issues,
        "duration_ms": duration_ms,
        "commands_executed": commands_executed,
        "content": [{"type": "text", "text": content_text}]
    }


# =============================================================================
# TOOL INFO
# =============================================================================

TOOLS_INFO = [
    {
        "name": "aos.vlan.audit",
        "description": "Audit VLAN configuration and find issues. "
                       "Use when: listing all VLANs, checking VLAN exists, finding disabled VLANs, auditing VLAN hygiene. "
                       "Returns: vlan_count, vlans[] with id/name/admin_state/oper_state/type, issues[], recommendations[]. "
                       "Combine with: aos.mac.lookup to find devices in a VLAN.",
        "input_schema": {
            "type": "object",
            "properties": {
                "host": {"type": "string", "description": "Switch IP address"},
                "vlan_id": {"type": "integer", "description": "Specific VLAN to audit (optional)"},
            },
            "required": ["host"]
        },
        "output_schema": {"type": "object"}
    },
    {
        "name": "aos.routing.audit",
        "description": "Audit IP routing including routes, VRFs, and OSPF neighbors. "
                       "Use when: checking routing table, verifying default route, troubleshooting routing issues, checking OSPF state. "
                       "Returns: route_total, routes[] (first 100) with destination/gateway/protocol/interface, vrfs[], ospf_neighbors[]. "
                       "Note: Large routing tables are truncated to 100 routes with total count provided.",
        "input_schema": {
            "type": "object",
            "properties": {
                "host": {"type": "string", "description": "Switch IP address"},
                "vrf": {"type": "string", "description": "Specific VRF to audit (optional)"},
            },
            "required": ["host"]
        },
        "output_schema": {"type": "object"}
    },
    {
        "name": "aos.spantree.audit",
        "description": "Audit Spanning Tree Protocol (STP) configuration. "
                       "Use when: checking STP mode (MSTP/RSTP), finding root bridge, identifying blocked ports, troubleshooting loops. "
                       "Returns: stp_mode, status (ON/OFF), designated_root, root_priority, port_states[] with role/state. "
                       "Important for: loop prevention verification, topology checks.",
        "input_schema": {
            "type": "object",
            "properties": {
                "host": {"type": "string", "description": "Switch IP address"},
            },
            "required": ["host"]
        },
        "output_schema": {"type": "object"}
    },
]
