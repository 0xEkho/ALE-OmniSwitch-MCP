"""System tools - Config backup, health monitoring, chassis status.

Tools: aos.config.backup, aos.health.monitor, aos.chassis.status
"""

import time
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from .base import create_device_from_host
from ..policy import compile_policy, sanitize_command
from ..config import AppConfig
from ..ssh_runner import SSHRunner
from ..health_parse import (
    parse_show_health, parse_show_chassis, parse_show_temperature,
    parse_show_fan, parse_show_power_supply, parse_show_cmm, analyze_chassis_health
)


# =============================================================================
# MODELS
# =============================================================================

class ArgsConfigBackup(BaseModel):
    host: str = Field(description="Target switch IP address")
    username: Optional[str] = Field(default=None, description="SSH username")
    port: Optional[int] = Field(default=22)


class ArgsHealthMonitor(BaseModel):
    host: str = Field(description="Target switch IP address")
    detailed: bool = Field(default=False, description="Include detailed health info")
    port: Optional[int] = Field(default=22)


class ArgsChassisStatus(BaseModel):
    host: str = Field(description="Target switch IP address")
    include_temperature: bool = Field(default=True)
    include_fans: bool = Field(default=True)
    include_power: bool = Field(default=True)
    port: Optional[int] = Field(default=22)


# =============================================================================
# HANDLERS
# =============================================================================

def handle_config_backup(
    cfg: AppConfig,
    runner: SSHRunner,
    args: Dict[str, Any],
    zone_resolver: Any = None,
) -> Dict[str, Any]:
    """Backup running configuration."""
    parsed = ArgsConfigBackup.model_validate(args)
    device = create_device_from_host(parsed.host, parsed.port or 22, parsed.username)
    
    start_time = time.time()
    cmd = "write terminal"
    res = runner.run(device, cmd, timeout_s=60, zone_resolver=zone_resolver)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"config_{parsed.host.replace('.', '_')}_{timestamp}.txt"
    config_text = res.stdout.strip()
    duration_ms = int((time.time() - start_time) * 1000)
    
    return {
        "host": parsed.host,
        "config": config_text,
        "size_bytes": len(config_text),
        "duration_ms": duration_ms,
        "timestamp": int(time.time()),
        "filename": filename,
        "commands_executed": [cmd],
        "content": [
            {
                "type": "text",
                "text": f"# Configuration Backup: {parsed.host}\n"
                       f"# Filename: {filename}\n"
                       f"# Size: {len(config_text)} bytes\n"
                       f"# Timestamp: {timestamp}\n"
                       f"# Duration: {duration_ms}ms\n\n"
                       f"```\n{config_text}\n```"
            }
        ]
    }


def handle_health_monitor(
    cfg: AppConfig,
    runner: SSHRunner,
    args: Dict[str, Any],
    zone_resolver: Any = None,
) -> Dict[str, Any]:
    """Monitor device health (CPU, memory, modules)."""
    parsed = ArgsHealthMonitor.model_validate(args)
    device = create_device_from_host(parsed.host, parsed.port or 22)
    compiled_policy = compile_policy(cfg.command_policy)
    
    start_time = time.time()
    commands_executed = []
    
    health_cmd = "show health all" if parsed.detailed else "show health"
    safe_cmd = sanitize_command(health_cmd, compiled_policy)
    health_result = runner.run(device, safe_cmd, timeout_s=15, zone_resolver=zone_resolver)
    commands_executed.append(health_cmd)
    
    health_data = parse_show_health(health_result.stdout)
    duration_ms = int((time.time() - start_time) * 1000)
    
    overall_status = health_data.get("overall_status", "UNKNOWN")
    modules = health_data.get("modules", [])
    issues = health_data.get("issues", [])
    
    # Build content
    status_emoji = "✅" if overall_status == "OK" else "⚠️" if overall_status == "WARNING" else "❌"
    content_text = (
        f"{status_emoji} **Health Monitor: {device.host}**\n\n"
        f"Overall Status: {overall_status}\n"
        f"Modules Monitored: {len(modules)}\n"
    )
    
    if modules:
        for mod in modules[:5]:
            mod_status = mod.get('status', 'N/A')
            mod_emoji = "✅" if mod_status == "OK" else "⚠️"
            content_text += f"\n{mod_emoji} {mod.get('name', 'Module')}: {mod_status}"
            if mod.get('cpu_percent'):
                content_text += f" (CPU: {mod['cpu_percent']}%)"
    
    if issues:
        content_text += f"\n\n⚠️ Issues ({len(issues)}):\n" + "\n".join(f"- {i}" for i in issues[:10])
    
    return {
        "host": device.host,
        "overall_status": overall_status,
        "modules": modules,
        "issues": issues,
        "duration_ms": duration_ms,
        "commands_executed": commands_executed,
        "content": [{"type": "text", "text": content_text}]
    }


def handle_chassis_status(
    cfg: AppConfig,
    runner: SSHRunner,
    args: Dict[str, Any],
    zone_resolver: Any = None,
) -> Dict[str, Any]:
    """Get chassis hardware status (temperature, fans, power)."""
    parsed = ArgsChassisStatus.model_validate(args)
    device = create_device_from_host(parsed.host, parsed.port or 22)
    compiled_policy = compile_policy(cfg.command_policy)
    
    start_time = time.time()
    commands_executed = []
    
    # Build command list
    commands = ["show chassis"]
    if parsed.include_temperature:
        commands.append("show temperature")
    if parsed.include_fans:
        commands.append("show fan")
    if parsed.include_power:
        commands.append("show power-supply")
    commands.append("show cmm")
    
    results = {}
    for cmd in commands:
        try:
            safe_cmd = sanitize_command(cmd, compiled_policy)
            res = runner.run(device, safe_cmd, timeout_s=15, zone_resolver=zone_resolver)
            results[cmd] = res.stdout
            commands_executed.append(cmd)
        except Exception:
            pass
    
    # Parse results
    chassis_data = parse_show_chassis(results.get("show chassis", ""))
    temp_data = parse_show_temperature(results.get("show temperature", "")) if "show temperature" in results else None
    fan_data = parse_show_fan(results.get("show fan", "")) if "show fan" in results else []
    psu_data = parse_show_power_supply(results.get("show power-supply", "")) if "show power-supply" in results else []
    cmm_data = parse_show_cmm(results.get("show cmm", "")) if "show cmm" in results else None
    
    # Analyze issues
    issues = analyze_chassis_health(chassis_data, temp_data or {}, fan_data, psu_data)
    if temp_data and temp_data.get("issues"):
        issues.extend(temp_data["issues"])
    
    duration_ms = int((time.time() - start_time) * 1000)
    
    # Build content
    content_text = (
        f"**Chassis Status: {device.host}**\n\n"
        f"Model: {chassis_data.get('chassis_type', 'Unknown')}\n"
        f"Serial: {chassis_data.get('serial_number', 'Unknown')}\n"
        f"MAC: {chassis_data.get('mac_address', 'Unknown')}\n"
        f"Hardware Rev: {chassis_data.get('hardware_revision', 'Unknown')}\n"
    )
    
    if cmm_data:
        content_text += "\n**CMM Status:**\n"
        if cmm_data.get("primary"):
            p = cmm_data["primary"]
            content_text += f"- Primary (Slot {p.get('slot', 'N/A')}): {p.get('status', 'N/A')}"
            if p.get("temperature_celsius"):
                content_text += f" - {p['temperature_celsius']}°C"
            content_text += "\n"
        if cmm_data.get("secondary"):
            s = cmm_data["secondary"]
            content_text += f"- Secondary (Slot {s.get('slot', 'N/A')}): {s.get('status', 'N/A')}"
            if s.get("temperature_celsius"):
                content_text += f" - {s['temperature_celsius']}°C"
            content_text += "\n"
    
    if temp_data:
        temp_val = temp_data.get("current_celsius") or temp_data.get("temperature")
        if temp_val:
            content_text += f"\nTemperature: {temp_val}°C"
    
    if fan_data:
        fans_ok = sum(1 for f in fan_data if f.get("status", "").lower() == "ok")
        content_text += f"\nFans: {fans_ok}/{len(fan_data)} OK"
    
    if psu_data:
        psu_ok = sum(1 for p in psu_data if p.get("status", "").lower() in ["ok", "up"])
        content_text += f"\nPower Supplies: {psu_ok}/{len(psu_data)} OK"
    
    if issues:
        content_text += f"\n\n⚠️ Hardware Issues ({len(issues)}):\n" + "\n".join(f"- {i}" for i in issues[:10])
    
    return {
        "host": device.host,
        "chassis_type": chassis_data.get("chassis_type"),
        "serial_number": chassis_data.get("serial_number"),
        "hardware_revision": chassis_data.get("hardware_revision"),
        "mac_address": chassis_data.get("mac_address"),
        "cmm": cmm_data,
        "temperature": temp_data,
        "fans": fan_data,
        "power_supplies": psu_data,
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
        "name": "aos.config.backup",
        "description": "Backup the running configuration to text. "
                       "Use when: saving config before changes, documenting current state, disaster recovery prep. "
                       "Returns: config_text (full running config), suggested_filename, line_count, size_bytes. "
                       "Note: Returns complete config - may be large. Use for backup/export purposes.",
        "input_schema": {
            "type": "object",
            "properties": {
                "host": {"type": "string", "description": "Switch IP address"},
                "username": {"type": "string", "description": "SSH username (optional)"},
            },
            "required": ["host"]
        },
        "output_schema": {"type": "object"}
    },
    {
        "name": "aos.health.monitor",
        "description": "Monitor device resource utilization and health metrics. "
                       "Use when: checking CPU/memory usage, diagnosing slow performance, capacity planning. "
                       "Returns: cpu_percent, memory_percent, memory_used_mb, memory_total_mb, module_status[]. "
                       "Combine with: aos.chassis.status for hardware health, aos.device.facts for device info.",
        "input_schema": {
            "type": "object",
            "properties": {
                "host": {"type": "string", "description": "Switch IP address"},
                "detailed": {"type": "boolean", "description": "Include detailed info", "default": False},
            },
            "required": ["host"]
        },
        "output_schema": {"type": "object"}
    },
    {
        "name": "aos.chassis.status",
        "description": "Get hardware health: temperature, fans, and power supplies. "
                       "Use when: checking for hardware alarms, monitoring environmental conditions, verifying PSU redundancy. "
                       "Returns: temperatures[] with sensor/value/status, fans[] with status/speed, power_supplies[] with status/watts. "
                       "Important for: datacenter monitoring, preventive maintenance, hardware troubleshooting.",
        "input_schema": {
            "type": "object",
            "properties": {
                "host": {"type": "string", "description": "Switch IP address"},
                "include_temperature": {"type": "boolean", "default": True},
                "include_fans": {"type": "boolean", "default": True},
                "include_power": {"type": "boolean", "default": True},
            },
            "required": ["host"]
        },
        "output_schema": {"type": "object"}
    },
]
