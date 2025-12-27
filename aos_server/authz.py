from __future__ import annotations

from typing import List, Set

from .api_models import RequestContext
from .config import AuthzConfig, Device


class AuthorizationError(PermissionError):
    pass


def _has_any_scope(granted: Set[str], required: List[str]) -> bool:
    if not required:
        return True
    return any(r in granted for r in required)


def authorize_tool(ctx: RequestContext, cfg: AuthzConfig, tool_name: str) -> None:
    # Skip authorization if scopes not configured in context
    if not hasattr(ctx, 'scopes'):
        return
    
    required = cfg.tool_scopes.get(tool_name, [])
    granted = set(ctx.scopes or [])

    if cfg.require_scopes and not granted:
        raise AuthorizationError("Missing scopes in request context")

    if not _has_any_scope(granted, required):
        raise AuthorizationError(f"Missing required scopes for tool {tool_name}: {required}")


def authorize_device(ctx: RequestContext, cfg: AuthzConfig, device: Device) -> None:
    if not cfg.enforce_device_authorization:
        return

    allowed_ids = set(ctx.allowed_device_ids or [])
    allowed_tags = set(ctx.allowed_tags or [])

    if not allowed_ids and not allowed_tags:
        raise AuthorizationError("Device authorization context is required")

    if allowed_ids and device.id in allowed_ids:
        return

    if allowed_tags and allowed_tags.intersection(set(device.tags)):
        return

    raise AuthorizationError(f"Not authorized for device {device.id}")
