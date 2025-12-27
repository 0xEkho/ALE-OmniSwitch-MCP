from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List

from .config import CommandPolicyConfig


_ANSI_RE = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")


@dataclass(frozen=True)
class CompiledCommandPolicy:
    allow: List[re.Pattern[str]]
    deny: List[re.Pattern[str]]
    max_command_length: int
    deny_multiline: bool
    strip_ansi: bool


def compile_policy(cfg: CommandPolicyConfig) -> CompiledCommandPolicy:
    return CompiledCommandPolicy(
        allow=[re.compile(p) for p in cfg.allow_regex],
        deny=[re.compile(p) for p in cfg.deny_regex],
        max_command_length=cfg.max_command_length,
        deny_multiline=cfg.deny_multiline,
        strip_ansi=cfg.strip_ansi,
    )


def sanitize_command(command: str, policy: CompiledCommandPolicy) -> str:
    if not isinstance(command, str) or not command.strip():
        raise ValueError("Command must be a non-empty string")

    cmd = command.strip()

    if policy.deny_multiline and ("\n" in cmd or "\r" in cmd):
        raise ValueError("Multiline commands are not allowed")

    if len(cmd) > policy.max_command_length:
        raise ValueError(f"Command too long (>{policy.max_command_length})")

    # NUL and other control chars can be used to confuse downstream parsers.
    if any(ord(ch) < 32 and ch not in ("\t",) for ch in cmd):
        raise ValueError("Control characters are not allowed")

    allowed = any(p.match(cmd) for p in policy.allow)
    if not allowed:
        raise ValueError("Command rejected by allowlist policy")

    denied = any(p.match(cmd) for p in policy.deny)
    if denied:
        raise ValueError("Command rejected by denylist policy")

    return cmd


def strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text)


def apply_redactions(text: str, redactions: List[dict]) -> str:
    """Apply redaction rules to a text output.

    redactions: list of {pattern: <regex>, replacement: <string>}
    """
    out = text
    for rule in redactions:
        pattern = rule.get("pattern")
        repl = rule.get("replacement", "***")
        if not pattern:
            continue
        out = re.sub(pattern, repl, out)
    return out
