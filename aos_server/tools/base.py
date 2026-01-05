"""Base models and helpers for AOS MCP tools.

This module contains shared Pydantic models, helper functions,
and common utilities used across all tool modules.
"""

from __future__ import annotations

import re
import string
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from ..config import Device, AuthPasswordInline


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def create_device_from_host(
    host: str,
    port: int = 22,
    username: Optional[str] = None
) -> Device:
    """Create a Device object from host parameters."""
    auth = AuthPasswordInline(password="") if username else None
    return Device(
        id=f"dynamic-{host}",
        host=host,
        port=port,
        username=username,
        auth=auth,
    )


def format_template(template: str, args: Dict[str, Any]) -> str:
    """Format a command template with arguments.
    
    Only replaces placeholders that exist in args.
    """
    class SafeFormatter(string.Formatter):
        def get_value(self, key, args, kwargs):
            if isinstance(key, str):
                return kwargs.get(key, f"{{{key}}}")
            return super().get_value(key, args, kwargs)
    
    formatter = SafeFormatter()
    return formatter.format(template, **args)


def extract_numeric(text: str) -> Optional[int]:
    """Extract first numeric value from text."""
    match = re.search(r'\d+', text)
    return int(match.group()) if match else None


# =============================================================================
# COMMON ARGUMENT MODELS
# =============================================================================

class ArgsHost(BaseModel):
    """Base arguments with just host."""
    host: str = Field(description="Target switch IP address or hostname")
    port: Optional[int] = Field(default=22, description="SSH port")


class ArgsHostCommand(ArgsHost):
    """Arguments with host and command."""
    command: str = Field(description="Command to execute")
    username: Optional[str] = Field(default=None, description="SSH username")
    timeout_s: Optional[int] = Field(default=None, description="Command timeout in seconds")


# =============================================================================
# COMMON OUTPUT MODELS
# =============================================================================

class ToolResult(BaseModel):
    """Base result with common fields."""
    host: str
    duration_ms: float = Field(description="Execution time in milliseconds")
    commands_executed: List[str] = Field(default_factory=list)


class ContentBlock(BaseModel):
    """MCP content block for rich rendering."""
    type: str = "text"
    text: str


# =============================================================================
# VLAN MODELS
# =============================================================================

class VlanInfo(BaseModel):
    """VLAN configuration for a port."""
    untagged: Optional[int] = Field(default=None, description="Untagged VLAN ID")
    tagged: List[int] = Field(default_factory=list, description="Tagged VLAN IDs")
    status: Optional[str] = Field(default=None, description="Port VLAN status")


# =============================================================================
# MAC ADDRESS MODELS
# =============================================================================

class MacAddressEntry(BaseModel):
    """MAC address learned on a port."""
    mac: str = Field(description="MAC address")
    vlan: int = Field(description="VLAN ID")
    type: str = Field(default="dynamic", description="Entry type (dynamic/static)")


# =============================================================================
# LLDP MODELS
# =============================================================================

class LldpNeighbor(BaseModel):
    """LLDP neighbor information."""
    chassis_id: str = Field(description="Neighbor chassis ID")
    port_id: str = Field(description="Neighbor port ID")
    port_description: Optional[str] = Field(default=None)
    system_name: Optional[str] = Field(default=None)
    system_description: Optional[str] = Field(default=None)
    management_ip: Optional[str] = Field(default=None)
    capabilities: Optional[str] = Field(default=None)


# =============================================================================
# POE MODELS
# =============================================================================

class PortPoeInfo(BaseModel):
    """PoE information for a port."""
    enabled: bool = Field(description="PoE administratively enabled")
    status: str = Field(description="PoE status (Powered/Searching/Disabled)")
    power_used_mw: int = Field(description="Power consumption in milliwatts")
    max_power_mw: int = Field(description="Maximum power allocation in milliwatts")
    device_class: Optional[str] = Field(default=None)
    priority: str = Field(description="PoE priority (Low/High/Critical)")


# =============================================================================
# PORT/INTERFACE MODELS
# =============================================================================

class PortStatistics(BaseModel):
    """Port traffic statistics."""
    rx_bytes: Optional[int] = None
    rx_unicast: Optional[int] = None
    rx_broadcast: Optional[int] = None
    rx_multicast: Optional[int] = None
    rx_errors: Optional[int] = None
    tx_bytes: Optional[int] = None
    tx_unicast: Optional[int] = None
    tx_broadcast: Optional[int] = None
    tx_multicast: Optional[int] = None
    tx_errors: Optional[int] = None


class InterfaceInfo(BaseModel):
    """Complete interface information."""
    port_id: str = Field(description="Port identifier (e.g., 1/1/1)")
    admin_state: str = Field(description="Administrative state")
    oper_state: str = Field(description="Operational state")
    speed: Optional[str] = None
    duplex: Optional[str] = None
    auto_neg: bool = True
    mtu: Optional[int] = None
    media_type: Optional[str] = None
    sfp_vendor: Optional[str] = None
    sfp_part_number: Optional[str] = None
    vlan: Optional[VlanInfo] = None
    mac_addresses: List[MacAddressEntry] = Field(default_factory=list)
    lldp_neighbor: Optional[LldpNeighbor] = None
    poe: Optional[PortPoeInfo] = None
    statistics: Optional[PortStatistics] = None
    description: Optional[str] = None


# =============================================================================
# DEVICE FACTS MODELS
# =============================================================================

class DeviceFacts(BaseModel):
    """Structured device facts from OmniSwitch."""
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
    hardware: Optional[Dict[str, Any]] = None
    lldp: Optional[Dict[str, Any]] = None


# =============================================================================
# AUDIT MODELS
# =============================================================================

class VlanAuditInfo(BaseModel):
    """VLAN audit information."""
    vlan_id: int
    name: Optional[str] = None
    admin_state: str = "enabled"
    oper_state: str = "active"
    port_count: int = 0
    mtu: int = 1500
    ip_interfaces: List[str] = Field(default_factory=list)


class VrfInfo(BaseModel):
    """VRF information for routing audit."""
    name: str
    rd: Optional[str] = None
    interfaces: List[str] = Field(default_factory=list)
    route_count: int = 0


class OspfNeighbor(BaseModel):
    """OSPF neighbor information."""
    neighbor_id: str
    state: str
    interface: str
    priority: int = 1
