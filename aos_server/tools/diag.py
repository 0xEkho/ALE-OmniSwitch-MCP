"""Diagnostic tools - Ping, Traceroute, PoE diagnostics and restart.

Tools: aos.diag.ping, aos.diag.traceroute, aos.diag.poe, aos.poe.restart
"""

import time
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from .base import create_device_from_host, format_template
from ..policy import compile_policy, sanitize_command, strip_ansi
from ..config import AppConfig
from ..ssh_runner import SSHRunner
from ..poe_parse import parse_show_lanpower


# =============================================================================
# MODELS
# =============================================================================

class ArgsPing(BaseModel):
    """Arguments for ping diagnostic."""
    host: str = Field(description="Target switch IP address")
    destination: str = Field(description="Ping destination IP or hostname")
    count: Optional[int] = Field(default=5, description="Number of ping packets")
    port: Optional[int] = Field(default=22, description="SSH port")
    timeout_s: Optional[int] = None


class ArgsTraceroute(BaseModel):
    """Arguments for traceroute diagnostic."""
    host: str = Field(description="Target switch IP address")
    destination: str = Field(description="Traceroute destination")
    port: Optional[int] = Field(default=22, description="SSH port")
    timeout_s: Optional[int] = None


class ArgsPoe(BaseModel):
    """Arguments for PoE diagnostics."""
    host: str = Field(description="Target switch IP address")
    slot: Optional[str] = Field(default=None, description="Slot to query (e.g., '1/1')")
    port: Optional[int] = Field(default=22, description="SSH port")


class ArgsPoeRestart(BaseModel):
    """Arguments for PoE port restart."""
    host: str = Field(description="Target switch IP address")
    port_id: str = Field(description="Port to restart (e.g., '1/1/1')")
    port: Optional[int] = Field(default=22, description="SSH port")
    username: Optional[str] = None
    wait_seconds: Optional[int] = Field(default=5, description="Seconds to wait between disable/enable")


class PoePortInfo(BaseModel):
    """PoE port information."""
    port: str = Field(alias="port_id")
    status: str
    power_mw: int = Field(alias="power_used_mw")
    max_power_mw: int
    priority: str
    poe_class: Optional[str] = Field(default=None, alias="device_class")

    class Config:
        populate_by_name = True


class PoEChassisSummary(BaseModel):
    """PoE chassis summary."""
    total_power_budget_watts: int
    power_budget_remaining_watts: int
    actual_power_consumed_watts: int


# =============================================================================
# HANDLERS
# =============================================================================

def handle_ping(
    cfg: AppConfig,
    runner: SSHRunner,
    args: Dict[str, Any],
    zone_resolver: Any = None,
) -> Dict[str, Any]:
    """Execute ping from switch to destination."""
    parsed = ArgsPing.model_validate(args)
    device = create_device_from_host(parsed.host, parsed.port or 22)
    
    compiled_policy = compile_policy(cfg.command_policy)
    cmd = format_template(cfg.templates.ping, {
        "destination": parsed.destination,
        "count": parsed.count,
    })
    cmd = sanitize_command(cmd, compiled_policy)
    res = runner.run(device, cmd, timeout_s=parsed.timeout_s, zone_resolver=zone_resolver)
    
    stdout = strip_ansi(res.stdout) if compiled_policy.strip_ansi else res.stdout
    
    return {
        "host": device.host,
        "command": cmd,
        "stdout": stdout,
        "stderr": res.stderr,
        "exit_status": res.exit_status,
        "duration_ms": res.duration_ms,
    }


def handle_traceroute(
    cfg: AppConfig,
    runner: SSHRunner,
    args: Dict[str, Any],
    zone_resolver: Any = None,
) -> Dict[str, Any]:
    """Execute traceroute from switch to destination."""
    parsed = ArgsTraceroute.model_validate(args)
    device = create_device_from_host(parsed.host, parsed.port or 22)
    
    compiled_policy = compile_policy(cfg.command_policy)
    cmd = format_template(cfg.templates.traceroute, {
        "destination": parsed.destination,
    })
    cmd = sanitize_command(cmd, compiled_policy)
    res = runner.run(device, cmd, timeout_s=parsed.timeout_s, zone_resolver=zone_resolver)
    
    stdout = strip_ansi(res.stdout) if compiled_policy.strip_ansi else res.stdout
    
    return {
        "host": device.host,
        "command": cmd,
        "stdout": stdout,
        "stderr": res.stderr,
        "exit_status": res.exit_status,
        "duration_ms": res.duration_ms,
    }


def handle_poe_diag(
    cfg: AppConfig,
    runner: SSHRunner,
    args: Dict[str, Any],
    zone_resolver: Any = None,
) -> Dict[str, Any]:
    """Get PoE status for a switch slot."""
    parsed = ArgsPoe.model_validate(args)
    device = create_device_from_host(parsed.host, parsed.port or 22)
    
    compiled_policy = compile_policy(cfg.command_policy)
    
    if parsed.slot:
        slot_num = parsed.slot.split('/')[0]
        raw_cmd = f"show lanpower slot {slot_num}/1"
    else:
        raw_cmd = "show lanpower slot 1/1"
    
    cmd = sanitize_command(raw_cmd, compiled_policy)
    res = runner.run(device, cmd, zone_resolver=zone_resolver)
    
    # Parse structured output
    parsed_poe = parse_show_lanpower(res.stdout)
    
    return {
        "host": device.host,
        "command": cmd,
        "ports": parsed_poe["ports"],
        "chassis_summary": parsed_poe["chassis_summary"],
        "duration_ms": res.duration_ms,
    }


def handle_poe_restart(
    cfg: AppConfig,
    runner: SSHRunner,
    args: Dict[str, Any],
    zone_resolver: Any = None,
) -> Dict[str, Any]:
    """Restart PoE on a specific port (disable then enable)."""
    parsed = ArgsPoeRestart.model_validate(args)
    device = create_device_from_host(parsed.host, parsed.port or 22, parsed.username)
    
    compiled_policy = compile_policy(cfg.command_policy)
    start_time = time.time()
    
    # Disable PoE
    stop_cmd = sanitize_command(
        f"lanpower port {parsed.port_id} admin-state disable",
        compiled_policy
    )
    stop_res = runner.run(device, stop_cmd, zone_resolver=zone_resolver)
    
    # Wait
    time.sleep(parsed.wait_seconds or 5)
    
    # Enable PoE
    start_cmd = sanitize_command(
        f"lanpower port {parsed.port_id} admin-state enable",
        compiled_policy
    )
    start_res = runner.run(device, start_cmd, zone_resolver=zone_resolver)
    
    duration_ms = int((time.time() - start_time) * 1000)
    success = stop_res.exit_status == 0 and start_res.exit_status == 0
    
    return {
        "host": device.host,
        "port_id": parsed.port_id,
        "wait_seconds": parsed.wait_seconds or 5,
        "stop_command": stop_cmd,
        "start_command": start_cmd,
        "stop_result": stop_res.stdout.strip() if stop_res.stdout else "OK",
        "start_result": start_res.stdout.strip() if start_res.stdout else "OK",
        "success": success,
        "duration_ms": duration_ms,
        "content": [
            {
                "type": "text",
                "text": f"{'✅' if success else '❌'} PoE restart on {parsed.port_id}: "
                       f"{'Success' if success else 'Failed'}\n"
                       f"Wait time: {parsed.wait_seconds or 5}s"
            }
        ]
    }


# =============================================================================
# TOOL INFO
# =============================================================================

TOOLS_INFO = [
    {
        "name": "aos.diag.ping",
        "description": "Execute ping FROM the OmniSwitch to test reachability. "
                       "Use when: testing if switch can reach a destination, verifying routing, checking network path. "
                       "Returns: packet_loss_pct, avg_rtt_ms, packets_sent/received. "
                       "Combine with: aos.diag.traceroute for path analysis.",
        "input_schema": {
            "type": "object",
            "properties": {
                "host": {"type": "string", "description": "Switch IP address"},
                "destination": {"type": "string", "description": "Ping destination"},
                "count": {"type": "integer", "description": "Number of packets", "default": 5},
            },
            "required": ["host", "destination"]
        },
        "output_schema": {"type": "object"}
    },
    {
        "name": "aos.diag.traceroute",
        "description": "Execute traceroute FROM the OmniSwitch to show network path. "
                       "Use when: diagnosing routing issues, finding path to destination, identifying slow hops. "
                       "Returns: list of hops with IP, hostname, rtt_ms. "
                       "Combine with: aos.diag.ping for connectivity + path analysis.",
        "input_schema": {
            "type": "object",
            "properties": {
                "host": {"type": "string", "description": "Switch IP address"},
                "destination": {"type": "string", "description": "Traceroute destination"},
            },
            "required": ["host", "destination"]
        },
        "output_schema": {"type": "object"}
    },
    {
        "name": "aos.diag.poe",
        "description": "Get Power over Ethernet (PoE) status for switch ports. "
                       "Use when: checking if PoE device is receiving power, troubleshooting IP phones/APs not powering on, auditing power budget. "
                       "Returns: per-port power_mw, max_power_mw, status, priority; chassis power_budget_w, power_consumed_w. "
                       "Combine with: aos.port.discover to correlate PoE with device identity.",
        "input_schema": {
            "type": "object",
            "properties": {
                "host": {"type": "string", "description": "Switch IP address"},
                "slot": {"type": "string", "description": "Slot to query (e.g., '1/1')"},
            },
            "required": ["host"]
        },
        "output_schema": {"type": "object"}
    },
    {
        "name": "aos.poe.restart",
        "description": "DESTRUCTIVE: Restart PoE on a port by power-cycling. "
                       "Use when: IP phone/AP frozen, PoE device unresponsive, need remote reboot without physical access. "
                       "Returns: success status, before/after power state. "
                       "WARNING: Causes brief outage for device on that port.",
        "input_schema": {
            "type": "object",
            "properties": {
                "host": {"type": "string", "description": "Switch IP address"},
                "port_id": {"type": "string", "description": "Port to restart (e.g., '1/1/1')"},
                "wait_seconds": {"type": "integer", "description": "Seconds between disable/enable", "default": 5},
            },
            "required": ["host", "port_id"]
        },
        "output_schema": {"type": "object"}
    },
]
