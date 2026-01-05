from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from .api_models import ToolCallRequest, ToolCallResponse, ToolsListResponse, MCPMetadata
from .config import AppConfig, EnvSettings, DeviceDefaults, load_config
from .inventory import InventoryStore
from .ssh_runner import SSHExecutionError, SSHRunner
from .tools import call_tool, tool_infos
from .mcp_sse import mcp_sse_endpoint


logger = logging.getLogger("aos_server")


def setup_logging() -> None:
    level = os.environ.get("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def _resolve_default_username(defaults: Optional[DeviceDefaults]) -> Optional[str]:
    if not defaults:
        return None
    if defaults.username_env:
        return os.environ.get(defaults.username_env)
    return defaults.username


def _resolve_default_auth(defaults: Optional[DeviceDefaults]):
    if not defaults:
        return None
    return defaults.auth


@dataclass
class AppState:
    env: EnvSettings
    cfg: AppConfig
    inv: InventoryStore
    runner: SSHRunner
    zone_resolver: Optional[Any] = None  # ZoneAuthResolver


def create_app() -> FastAPI:
    setup_logging()
    env = EnvSettings()

    cfg = load_config(env.config_file)
    inv = InventoryStore.from_config(cfg.inventory)

    snap = inv.snapshot()
    defaults = cfg.inventory.device_defaults

    runner = SSHRunner(
        cfg.ssh,
        jump_hosts=snap.jumps_by_name,
        default_device_username=_resolve_default_username(defaults),
        default_device_auth=_resolve_default_auth(defaults),
    )

    # Initialize zone auth resolver if configured
    zone_resolver = None
    if cfg.zone_auth:
        from .zone_auth import ZoneAuthResolver
        zone_config = {}
        if cfg.zone_auth.global_:
            zone_config['global'] = cfg.zone_auth.global_.model_dump(exclude_none=True)
        if cfg.zone_auth.zones:
            zone_config['zones'] = {
                zone_id: zone_cfg.model_dump(exclude_none=True)
                for zone_id, zone_cfg in cfg.zone_auth.zones.items()
            }
        zone_resolver = ZoneAuthResolver(zone_config)
        logger.info("Zone-based authentication enabled")

    state = AppState(env=env, cfg=cfg, inv=inv, runner=runner, zone_resolver=zone_resolver)

    # Initialize rate limiter
    limiter = Limiter(key_func=get_remote_address, default_limits=[f"{env.rate_limit_per_minute}/minute"])

    app = FastAPI(
        title="ALE OmniSwitch MCP Server",
        version="1.2.0",
        description="MCP server for Alcatel-Lucent Enterprise OmniSwitch network devices. "
                    "Provides 20 production-ready network management tools for AI assistants.",
        docs_url="/docs",  # Swagger UI
        redoc_url="/redoc",  # ReDoc
        openapi_url="/openapi.json",  # OpenAPI spec
    )

    # Add rate limiter to app state
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    def get_state() -> AppState:
        return state

    @app.get("/healthz")
    async def healthz():
        return {"status": "ok"}

    @app.get("/mcp/metadata")
    async def mcp_metadata():
        """MCP platform metadata endpoint for capability discovery."""
        return MCPMetadata().model_dump()

    @app.post("/mcp/sse")
    @limiter.limit(f"{env.rate_limit_per_minute}/minute")
    async def mcp_sse(request: Request, st: AppState = Depends(get_state)):
        """MCP SSE endpoint for Open WebUI native integration.
        
        This endpoint implements the MCP HTTP Streamable protocol using
        Server-Sent Events (SSE) for compatibility with Open WebUI v0.6.31+.
        
        Security features:
        - IP whitelisting via AOS_ALLOWED_IPS environment variable
        - Bearer token authentication via Authorization header
        - Rate limiting per IP address
        
        Open WebUI Configuration:
        1. Go to Admin Panel → Settings → External Tools
        2. Add MCP Server:
           - Type: MCP (Streamable HTTP)
           - Server URL: http://your-server:8080/mcp/sse
           - Auth: Bearer <your-token> (if AOS_INTERNAL_API_KEY is set)
        3. Save and restart Open WebUI
        """
        # Extract Bearer token if configured
        api_key = None
        if st.env.internal_api_key:
            api_key = st.env.internal_api_key.get_secret_value()
        
        return await mcp_sse_endpoint(
            request=request,
            cfg=st.cfg,
            inv=st.inv,
            runner=st.runner,
            zone_resolver=st.zone_resolver,
            allowed_ips=st.env.allowed_ips,
            api_key=api_key,
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        # Avoid leaking internal details to callers by default.
        logger.exception("unhandled_exception", extra={"path": str(request.url.path)})
        return JSONResponse(
            status_code=500,
            content=ToolCallResponse(
                status="error",
                error={"code": "internal_error", "message": "Internal server error"},
            ).model_dump(),
        )

    def require_internal_api_key(
        st: AppState = Depends(get_state),
        x_internal_api_key: Optional[str] = Header(default=None, alias="X-Internal-Api-Key"),
    ):
        expected = st.env.internal_api_key.get_secret_value() if st.env.internal_api_key else None
        if expected is None:
            return
        if not x_internal_api_key or x_internal_api_key != expected:
            raise HTTPException(status_code=401, detail="Missing or invalid X-Internal-Api-Key")

    @app.post("/v1/tools/list", dependencies=[Depends(require_internal_api_key)])
    async def tools_list(
        request: Request,
        st: AppState = Depends(get_state),
    ):
        """List all available tools.
        
        Accepts 'compact' and 'ultra_compact' flags via:
        - Query params: ?compact=true&ultra_compact=false
        - JSON body: {"compact": true, "ultra_compact": false}
        
        Modes:
        - ultra_compact=true: Only tool names (19 lines, minimal tokens)
        - compact=true: Names + short descriptions (80 lines, default)
        - compact=false: Full schemas with input/output (518 lines, for devs)
        """
        # Try to get flags from body first, fallback to query params
        body = {}
        try:
            body = await request.json()
        except:
            pass
        
        # Check query params
        query_params = dict(request.query_params)
        
        # Priority: body > query params > defaults
        ultra_compact = body.get('ultra_compact') or query_params.get('ultra_compact') == 'true'
        compact = body.get('compact', True) if 'compact' in body else (query_params.get('compact', 'true') != 'false')
        
        tools = tool_infos(st.cfg)
        
        if ultra_compact:
            # Ultra minimal: only names (for LLM discovery to avoid token explosion)
            return {"tools": [t.name for t in tools]}
        
        if compact:
            # Return minimal version for LLMs (avoid token explosion)
            minimal_tools = [
                {
                    "name": t.name,
                    "description": t.description.split('.')[0] + '.' if '.' in t.description else t.description[:80]
                }
                for t in tools
            ]
            return {"tools": minimal_tools}
        
        return ToolsListResponse(tools=tools).model_dump()

    @app.post("/v1/tools/call", dependencies=[Depends(require_internal_api_key)])
    async def tools_call(req: ToolCallRequest, request: Request, st: AppState = Depends(get_state)):
        # If configured, fail closed when context is missing (platform integration bug).
        if st.env.require_authz_context:
            if not req.context or (not req.context.subject and not req.context.scopes):
                raise HTTPException(status_code=400, detail="Missing authz context")

        try:
            data = call_tool(
                cfg=st.cfg,
                inv=st.inv,
                runner=st.runner,
                ctx=req.context,
                tool=req.tool,
                args=req.args,
                zone_resolver=st.zone_resolver,
            )
            
            # Extract content blocks if provided by tool
            content_blocks = data.pop("content", None) if "content" in data else None
            
            return ToolCallResponse(
                status="ok",
                data=data,
                content=content_blocks,
                meta={"tool": req.tool}
            ).model_dump()
        except HTTPException:
            raise
        except KeyError as e:
            return ToolCallResponse(
                status="error",
                error={"code": "unknown_tool", "message": str(e)},
                meta={"tool": req.tool},
            ).model_dump()
        except ValueError as e:
            return ToolCallResponse(
                status="error",
                error={"code": "invalid_request", "message": str(e)},
                meta={"tool": req.tool},
            ).model_dump()
        except PermissionError as e:
            return ToolCallResponse(
                status="error",
                error={"code": "not_authorized", "message": str(e)},
                meta={"tool": req.tool},
            ).model_dump()
        except SSHExecutionError as e:
            return ToolCallResponse(
                status="error",
                error={"code": "ssh_error", "message": str(e)},
                meta={"tool": req.tool},
            ).model_dump()
        except Exception as e:
            logger.exception("tool_call_failed", extra={"tool": req.tool})
            return ToolCallResponse(
                status="error",
                error={"code": "internal_error", "message": "Internal server error"},
                meta={"tool": req.tool},
            ).model_dump()

    return app
