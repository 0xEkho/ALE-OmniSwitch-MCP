"""CLI tool - Execute read-only commands on OmniSwitch.

Tool: aos.cli.readonly
"""

from typing import Any, Dict, Optional
from pydantic import BaseModel, Field

from .base import create_device_from_host
from ..policy import apply_redactions, compile_policy, sanitize_command, strip_ansi
from ..config import AppConfig
from ..ssh_runner import SSHRunner


# =============================================================================
# MODELS
# =============================================================================

class ArgsCliReadonly(BaseModel):
    """Arguments for CLI readonly tool."""
    host: str = Field(description="Target switch IP address or hostname")
    command: str = Field(description="Read-only command to execute")
    port: Optional[int] = Field(default=22, description="SSH port")
    username: Optional[str] = Field(default=None, description="SSH username")
    timeout_s: Optional[int] = Field(default=None, description="Command timeout")


class ResultCliReadonly(BaseModel):
    """Result of CLI readonly execution."""
    host: str
    command: str
    stdout: str
    stderr: str
    exit_status: Optional[int] = None
    duration_ms: float
    truncated: bool = False
    redacted: bool = False


# =============================================================================
# HANDLER
# =============================================================================

def handle_cli_readonly(
    cfg: AppConfig,
    runner: SSHRunner,
    args: Dict[str, Any],
    zone_resolver: Any = None,
) -> Dict[str, Any]:
    """Execute a read-only CLI command on an OmniSwitch.
    
    Returns the command output with optional redaction of sensitive data.
    """
    parsed = ArgsCliReadonly.model_validate(args)
    device = create_device_from_host(parsed.host, parsed.port or 22, parsed.username)
    
    compiled_policy = compile_policy(cfg.command_policy)
    cmd = sanitize_command(parsed.command, compiled_policy)
    res = runner.run(device, cmd, timeout_s=parsed.timeout_s, zone_resolver=zone_resolver)
    
    stdout = res.stdout
    stderr = res.stderr
    redacted = False
    
    # Strip ANSI codes if configured
    if compiled_policy.strip_ansi:
        stdout = strip_ansi(stdout)
        stderr = strip_ansi(stderr)
    
    # Apply redactions if configured
    if cfg.command_policy.redactions:
        stdout2 = apply_redactions(stdout, cfg.command_policy.redactions)
        stderr2 = apply_redactions(stderr, cfg.command_policy.redactions)
        redacted = (stdout2 != stdout) or (stderr2 != stderr)
        stdout, stderr = stdout2, stderr2
    
    return {
        "host": device.host,
        "command": cmd,
        "stdout": stdout,
        "stderr": stderr,
        "exit_status": res.exit_status,
        "duration_ms": res.duration_ms,
        "truncated": res.truncated,
        "redacted": redacted,
    }


# =============================================================================
# TOOL INFO
# =============================================================================

TOOL_INFO = {
    "name": "aos.cli.readonly",
    "description": "Execute any read-only CLI command on an ALE OmniSwitch. "
                   "USE ONLY AS FALLBACK when specialized tools don't exist for your task. "
                   "Prefer: aos.device.facts (device info), aos.lldp.neighbors (connected devices), "
                   "aos.mac.lookup (find devices), aos.vlan.audit (VLANs), aos.diag.ping (connectivity). "
                   "Returns: raw stdout text. Common commands: 'show system', 'show vlan', 'show interfaces'.",
    "input_schema": {
        "type": "object",
        "properties": {
            "host": {
                "type": "string",
                "description": "Target switch IP address or hostname"
            },
            "command": {
                "type": "string",
                "description": "Read-only CLI command (e.g., 'show vlan', 'show interfaces')"
            },
            "port": {
                "type": "integer",
                "description": "SSH port (default: 22)",
                "default": 22
            },
            "username": {
                "type": "string",
                "description": "SSH username (optional, uses default if not provided)"
            },
            "timeout_s": {
                "type": "integer",
                "description": "Command timeout in seconds"
            }
        },
        "required": ["host", "command"]
    },
    "output_schema": {
        "type": "object",
        "properties": {
            "host": {"type": "string"},
            "command": {"type": "string"},
            "stdout": {"type": "string", "description": "Command output"},
            "stderr": {"type": "string"},
            "duration_ms": {"type": "number"},
            "redacted": {"type": "boolean", "description": "Whether sensitive data was redacted"}
        }
    }
}
