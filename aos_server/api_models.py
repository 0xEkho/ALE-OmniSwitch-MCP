from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class RequestContext(BaseModel):
    # Identifiers passed from your MCP platform
    subject: Optional[str] = Field(default=None, description="User identifier (email, username) for audit logging")
    environment: Optional[str] = Field(default=None, description="Environment (TEST, PROD) from IPAM for audit logging")
    correlation_id: Optional[str] = Field(default=None, description="Request tracing ID")
    client: Optional[str] = Field(default=None, description="Client application identifier")


class ToolCallRequest(BaseModel):
    context: RequestContext
    tool: str
    args: Dict[str, Any] = Field(default_factory=dict)


class ToolCallError(BaseModel):
    code: str
    message: str
    details: Optional[Dict[str, Any]] = None


class ToolCallResponse(BaseModel):
    status: Literal["ok", "error"]
    data: Optional[Dict[str, Any]] = None
    content: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="MCP-compatible content blocks for rich client rendering"
    )
    warnings: List[str] = Field(default_factory=list)
    error: Optional[ToolCallError] = None
    meta: Dict[str, Any] = Field(default_factory=dict)


class ToolInfo(BaseModel):
    name: str
    description: str
    input_schema: Dict[str, Any]
    output_schema: Dict[str, Any]
    required_scopes: List[str] = Field(default_factory=list)


class ToolsListResponse(BaseModel):
    tools: List[ToolInfo]


class MCPMetadata(BaseModel):
    """MCP platform metadata endpoint response."""
    protocol_version: str = "1.0"
    server_name: str = "aos-server"
    server_version: str = "0.2.0"
    vendor: str = "Alcatel-Lucent Enterprise"
    capabilities: List[str] = Field(default_factory=lambda: [
        "tools",
        "ssh_execution",
        "poe_diagnostics"
    ])
    description: str = "Pure SSH executor for OmniSwitch devices. Requires IPAM MCP for device discovery."
