from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse

from .api_models import ToolCallRequest, ToolCallResponse, ToolsListResponse, MCPMetadata
from .config import AppConfig, EnvSettings, DeviceDefaults, load_config
from .inventory import InventoryStore
from .ssh_runner import SSHExecutionError, SSHRunner
from .tools import call_tool, tool_infos


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

    app = FastAPI(title="AOS Server (for MCP Platform)", version="0.1.2.1")

    def get_state() -> AppState:
        return state

    @app.get("/healthz")
    async def healthz():
        return {"status": "ok"}

    @app.get("/mcp/metadata")
    async def mcp_metadata():
        """MCP platform metadata endpoint for capability discovery."""
        return MCPMetadata().model_dump()

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
    async def tools_list(st: AppState = Depends(get_state)):
        return ToolsListResponse(tools=tool_infos(st.cfg)).model_dump()

    @app.post("/v1/tools/call", dependencies=[Depends(require_internal_api_key)])
    async def tools_call(req: ToolCallRequest, st: AppState = Depends(get_state)):
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
            
            # Build MCP content blocks for rich rendering
            content_blocks = []
            
            # Extract content if tool provides it in data
            if "content" in data and data["content"]:
                content_blocks = data.pop("content")  # Remove from data, use at root level
            elif req.tool == "aos.cli.readonly" and data.get("stdout"):
                content_blocks.append({
                    "type": "text",
                    "text": data["stdout"]
                })
            elif req.tool == "aos.diag.poe" and data.get("ports"):
                # Format PoE data as structured text
                poe_text = f"**PoE Status for {data.get('host', 'unknown')}**\n\n"
                if data.get("chassis_summary"):
                    cs = data["chassis_summary"]
                    poe_text += "**Chassis Summary:**\n"
                    poe_text += f"- Power Consumed: {cs.get('actual_power_consumed_watts', 0)}W\n"
                    poe_text += f"- Budget Remaining: {cs.get('power_budget_remaining_watts', 0)}W\n"
                    poe_text += f"- Total Budget: {cs.get('total_power_budget_watts', 0)}W\n\n"
                poe_text += f"**Ports:** {len(data['ports'])} ports analyzed\n"
                content_blocks.append({"type": "text", "text": poe_text})
            elif req.tool == "aos.device.facts" and data.get("facts"):
                facts = data["facts"]
                facts_text = f"**Device Facts: {data.get('host', 'unknown')}**\n\n"
                if facts.get("model"):
                    facts_text += f"Model: {facts['model']}\n"
                if facts.get("serial_number"):
                    facts_text += f"Serial: {facts['serial_number']}\n"
                if facts.get("software_version"):
                    facts_text += f"Software: {facts['software_version']}\n"
                content_blocks.append({"type": "text", "text": facts_text})
            
            return ToolCallResponse(
                status="ok",
                data=data,
                content=content_blocks if content_blocks else None,
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
        except Exception:
            logger.exception("tool_call_failed", extra={"tool": req.tool})
            return ToolCallResponse(
                status="error",
                error={"code": "internal_error", "message": "Internal server error"},
                meta={"tool": req.tool},
            ).model_dump()

    return app
