"""AOS MCP Tools Package.

This package provides all MCP tools for OmniSwitch management.
Tools are organized by category for better maintainability.

Categories:
- cli: Command line interface (aos.cli.readonly)
- diag: Diagnostics (aos.diag.ping, traceroute, poe, poe.restart)
- device: Device info (aos.device.facts, port.info, port.discover, interfaces.discover)
- audit: Config audit (aos.vlan.audit, routing.audit, spantree.audit)
- network: Network services (aos.mac.lookup, lacp.info, ntp.status, dhcp.relay.info)
- system: System management (aos.config.backup, health.monitor, chassis.status)
"""

from typing import Any, Dict, List, Optional

from ..api_models import RequestContext, ToolInfo
from ..config import AppConfig
from ..inventory import InventoryStore
from ..ssh_runner import SSHRunner

# Import handlers from submodules
from .cli import handle_cli_readonly, TOOL_INFO as CLI_TOOL_INFO
from .diag import (
    handle_ping,
    handle_traceroute,
    handle_poe_diag,
    handle_poe_restart,
    TOOLS_INFO as DIAG_TOOLS_INFO,
)
from .device import (
    handle_device_facts,
    handle_port_info,
    handle_port_discover,
    handle_interfaces_discover,
    TOOLS_INFO as DEVICE_TOOLS_INFO,
)
from .audit import (
    handle_vlan_audit,
    handle_routing_audit,
    handle_spantree_audit,
    TOOLS_INFO as AUDIT_TOOLS_INFO,
)
from .network import (
    handle_mac_lookup,
    handle_lacp_info,
    handle_ntp_status,
    handle_dhcp_relay_info,
    handle_lldp_neighbors,
    TOOLS_INFO as NETWORK_TOOLS_INFO,
)
from .system import (
    handle_config_backup,
    handle_health_monitor,
    handle_chassis_status,
    TOOLS_INFO as SYSTEM_TOOLS_INFO,
)


# =============================================================================
# TOOL REGISTRY
# =============================================================================

# Map tool names to handlers
TOOL_HANDLERS = {
    # CLI
    "aos.cli.readonly": handle_cli_readonly,
    # Diagnostics
    "aos.diag.ping": handle_ping,
    "aos.diag.traceroute": handle_traceroute,
    "aos.diag.poe": handle_poe_diag,
    "aos.poe.restart": handle_poe_restart,
    # Device
    "aos.device.facts": handle_device_facts,
    "aos.port.info": handle_port_info,
    "aos.port.discover": handle_port_discover,
    "aos.interfaces.discover": handle_interfaces_discover,
    # Audit
    "aos.vlan.audit": handle_vlan_audit,
    "aos.routing.audit": handle_routing_audit,
    "aos.spantree.audit": handle_spantree_audit,
    # Network
    "aos.mac.lookup": handle_mac_lookup,
    "aos.lacp.info": handle_lacp_info,
    "aos.ntp.status": handle_ntp_status,
    "aos.dhcp.relay.info": handle_dhcp_relay_info,
    "aos.lldp.neighbors": handle_lldp_neighbors,
    # System
    "aos.config.backup": handle_config_backup,
    "aos.health.monitor": handle_health_monitor,
    "aos.chassis.status": handle_chassis_status,
}

# Collect all tool info
ALL_TOOLS_INFO = (
    [CLI_TOOL_INFO]
    + DIAG_TOOLS_INFO
    + DEVICE_TOOLS_INFO
    + AUDIT_TOOLS_INFO
    + NETWORK_TOOLS_INFO
    + SYSTEM_TOOLS_INFO
)


# =============================================================================
# PUBLIC API
# =============================================================================

def call_tool(
    cfg: AppConfig,
    inv: InventoryStore,
    runner: SSHRunner,
    ctx: Optional[RequestContext],
    tool: str,
    args: Dict[str, Any],
    zone_resolver: Any = None,
) -> Dict[str, Any]:
    """Execute a tool by name.
    
    Args:
        cfg: Application configuration
        inv: Inventory store
        runner: SSH runner
        ctx: Request context (user, correlation ID)
        tool: Tool name (e.g., 'aos.device.facts')
        args: Tool arguments
        zone_resolver: Optional zone auth resolver
        
    Returns:
        Tool result as dictionary
        
    Raises:
        KeyError: If tool not found
        ValueError: If arguments invalid
        PermissionError: If not authorized
    """
    if tool not in TOOL_HANDLERS:
        raise KeyError(f"Unknown tool: {tool}")
    
    handler = TOOL_HANDLERS[tool]
    return handler(cfg, runner, args, zone_resolver)


def tool_infos(cfg: Optional[AppConfig] = None) -> List[ToolInfo]:
    """Get list of all available tools.
    
    Args:
        cfg: Optional config for filtering tools
        
    Returns:
        List of ToolInfo objects
    """
    tools = [
        ToolInfo(
            name=info["name"],
            description=info["description"],
            input_schema=info["input_schema"],
            output_schema=info.get("output_schema", {}),
            required_scopes=info.get("required_scopes", []),
        )
        for info in ALL_TOOLS_INFO
    ]
    return sorted(tools, key=lambda t: t.name)


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "call_tool",
    "tool_infos",
    "TOOL_HANDLERS",
]
