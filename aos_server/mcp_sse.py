"""MCP SSE (Server-Sent Events) endpoint for Open WebUI native integration.

This module provides a Server-Sent Events endpoint compatible with
Open WebUI's native MCP HTTP Streamable protocol support.
"""

from __future__ import annotations

import json
import logging
from typing import Any, AsyncGenerator, Dict, Optional

from fastapi import HTTPException, Request
from fastapi.responses import StreamingResponse

from .config import AppConfig
from .inventory import InventoryStore
from .ssh_runner import SSHRunner
from .tools import call_tool, tool_infos

logger = logging.getLogger("aos_server.mcp_sse")


class MCPSSEHandler:
    """Handler for MCP Server-Sent Events protocol."""

    def __init__(
        self,
        cfg: AppConfig,
        inv: InventoryStore,
        runner: SSHRunner,
        zone_resolver: Optional[Any] = None,
        user_context: Optional[Dict[str, str]] = None,
    ):
        self.cfg = cfg
        self.inv = inv
        self.runner = runner
        self.zone_resolver = zone_resolver
        self.user_context = user_context or {}

    async def handle_initialize(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle MCP initialize request."""
        return {
            "protocolVersion": "2024-11-05",
            "serverInfo": {
                "name": "aos-server",
                "version": "1.2.0",
                "vendor": "Alcatel-Lucent Enterprise",
            },
            "capabilities": {
                "tools": {},
            },
        }

    async def handle_tools_list(self) -> Dict[str, Any]:
        """Handle MCP tools/list request."""
        tools = tool_infos(self.cfg)
        return {
            "tools": [
                {
                    "name": tool.name,
                    "description": tool.description,
                    "inputSchema": tool.input_schema,
                }
                for tool in tools
            ]
        }

    async def handle_tools_call(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle MCP tools/call request."""
        tool_name = params.get("name")
        arguments = params.get("arguments", {})

        # Extract context (optional in Open WebUI)
        from .api_models import RequestContext

        # Enhanced logging with user context (from HTTP headers or _meta)
        user_info = params.get("_meta", {})
        
        subject = user_info.get("subject", "anonymous")
        correlation_id = self.user_context.get("request_id", user_info.get("requestId", "unknown"))
        
        logger.info(
            f"Tool call: {tool_name} | User: {subject} | CorrelationID: {correlation_id}",
            extra={
                "tool": tool_name,
                "subject": subject,
                "correlation_id": correlation_id,
                "arguments": arguments,
            }
        )

        ctx = RequestContext(
            subject=subject if subject != "anonymous" else None,
            correlation_id=correlation_id if correlation_id != "unknown" else None,
        )

        try:
            # Call the tool
            data = call_tool(
                cfg=self.cfg,
                inv=self.inv,
                runner=self.runner,
                ctx=ctx,
                tool=tool_name,
                args=arguments,
                zone_resolver=self.zone_resolver,
            )

            # Format response as MCP content
            content = []

            # Extract or build content blocks
            if "content" in data and data["content"]:
                content = data.pop("content")
            elif "stdout" in data:
                content.append({"type": "text", "text": data["stdout"]})
            else:
                # Convert data to JSON text for display
                content.append({"type": "text", "text": json.dumps(data, indent=2)})

            logger.info(
                f"Tool call success: {tool_name} | User: {subject}",
                extra={"tool": tool_name, "subject": subject, "status": "success"}
            )

            return {"content": content, "isError": False}

        except Exception as e:
            logger.exception(
                f"Tool call failed: {tool_name} | User: {subject} | Error: {str(e)}",
                extra={"tool": tool_name, "subject": subject, "error": str(e)}
            )

            return {
                "content": [
                    {"type": "text", "text": f"Error executing {tool_name}: {str(e)}"}
                ],
                "isError": True,
            }

    async def stream_response(
        self, request_data: Dict[str, Any]
    ) -> AsyncGenerator[str, None]:
        """Stream MCP SSE responses."""
        method = request_data.get("method")
        params = request_data.get("params", {})

        try:
            if method == "initialize":
                result = await self.handle_initialize(params)
            elif method == "tools/list":
                result = await self.handle_tools_list()
            elif method == "tools/call":
                result = await self.handle_tools_call(params)
            else:
                result = {
                    "error": {"code": -32601, "message": f"Method not found: {method}"}
                }

            # Format as SSE event
            response = {
                "jsonrpc": "2.0",
                "id": request_data.get("id"),
                "result": result,
            }

            yield f"data: {json.dumps(response)}\n\n"

        except Exception as e:
            logger.exception(f"SSE stream error for method {method}")
            error_response = {
                "jsonrpc": "2.0",
                "id": request_data.get("id"),
                "error": {"code": -32603, "message": str(e)},
            }
            yield f"data: {json.dumps(error_response)}\n\n"


async def mcp_sse_endpoint(
    request: Request,
    cfg: AppConfig,
    inv: InventoryStore,
    runner: SSHRunner,
    zone_resolver: Optional[Any] = None,
    allowed_ips: Optional[str] = None,
    api_key: Optional[str] = None,
) -> StreamingResponse:
    """MCP SSE endpoint handler for Open WebUI integration.

    This endpoint implements the MCP HTTP Streamable protocol using
    Server-Sent Events (SSE) for compatibility with Open WebUI v0.6.31+.
    
    Security:
    - IP whitelisting via allowed_ips parameter
    - Bearer token authentication via Authorization header
    
    User Context:
    - X-User-Email: User email from OpenWebUI (e.g., admin@company.com)
    - X-User-Name: User display name
    - X-Request-ID: Request correlation ID for tracing
    """
    # 1. IP Whitelisting
    if allowed_ips:
        client_ip = request.client.host if request.client else None
        if client_ip and not _is_ip_allowed(client_ip, allowed_ips):
            logger.warning(f"Access denied for IP: {client_ip}")
            raise HTTPException(status_code=403, detail="Access denied: IP not whitelisted")
    
    # 2. Bearer Token Authentication
    if api_key:
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer ") or auth_header[7:] != api_key:
            logger.warning("Invalid or missing Bearer token")
            raise HTTPException(status_code=401, detail="Invalid or missing Bearer token")
    
    # 3. Extract minimal context
    user_context = {
        "request_id": request.headers.get("X-Request-ID", f"req-{id(request)}"),
    }
    
    try:
        # Parse JSON-RPC request
        body = await request.json()
        
        handler = MCPSSEHandler(cfg, inv, runner, zone_resolver, user_context)

        return StreamingResponse(
            handler.stream_response(body),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",  # Disable nginx buffering
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to handle MCP SSE request")
        # Return error as SSE
        async def error_stream():
            error = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": f"Parse error: {str(e)}"},
            }
            yield f"data: {json.dumps(error)}\n\n"

        return StreamingResponse(
            error_stream(),
            media_type="text/event-stream",
        )


def _is_ip_allowed(client_ip: str, allowed_cidrs: str) -> bool:
    """Check if client IP is in allowed CIDRs list.
    
    Args:
        client_ip: Client IP address (e.g., "192.168.1.50")
        allowed_cidrs: Comma-separated CIDR list (e.g., "10.0.0.0/8,127.0.0.1/32")
    
    Returns:
        True if IP is allowed, False otherwise
    """
    import ipaddress
    
    try:
        client_addr = ipaddress.ip_address(client_ip)
        for cidr in allowed_cidrs.split(","):
            cidr = cidr.strip()
            if not cidr:
                continue
            network = ipaddress.ip_network(cidr, strict=False)
            if client_addr in network:
                return True
        return False
    except ValueError as e:
        logger.error(f"Invalid IP/CIDR format: {e}")
        return False
