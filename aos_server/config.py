from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field, SecretStr, ValidationError
from pydantic_settings import BaseSettings


class EnvSettings(BaseSettings):
    """Runtime settings provided via environment variables."""

    config_file: str = Field(default="config.yaml", alias="AOS_CONFIG_FILE")

    # Optional internal API auth (recommended when the service is behind your MCP platform)
    internal_api_key: Optional[SecretStr] = Field(default=None, alias="AOS_INTERNAL_API_KEY")

    # If true, reject requests that don't include authz context (subject + scopes)
    require_authz_context: bool = Field(default=False, alias="AOS_REQUIRE_AUTHZ_CONTEXT")

    model_config = {
        "extra": "ignore",
        "case_sensitive": True,
    }


class AuthPasswordEnv(BaseModel):
    type: Literal["password_env"]
    env: str


class AuthPasswordInline(BaseModel):
    # Discouraged in production. Prefer password_env or a secret manager integration.
    type: Literal["password_inline"]
    password: SecretStr


class AuthPrivateKeyFile(BaseModel):
    type: Literal["private_key_file"]
    private_key_file: str
    passphrase_env: Optional[str] = None


DeviceAuth = Union[AuthPasswordEnv, AuthPasswordInline, AuthPrivateKeyFile]


class JumpHost(BaseModel):
    name: str
    host: str
    port: int = 22
    username: str
    auth: DeviceAuth
    tags: List[str] = Field(default_factory=list)


class Device(BaseModel):
    """A target network device.

    username/auth may be omitted when inventory.device_defaults is configured. This enables a
    simplified configuration model where a single RADIUS (read-only) credential pair is applied to
    all devices.
    """

    id: str
    host: str
    port: int = 22

    username: Optional[str] = None
    auth: Optional[DeviceAuth] = None

    name: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    jump: Optional[str] = None  # JumpHost.name

    # Optional non-sensitive metadata collected by discovery/facts tools.
    facts: Optional[Dict[str, Any]] = None


class DeviceDefaults(BaseModel):
    """Default connection parameters for devices.

    Typical production use:
      - username_env: AOS_DEVICE_USERNAME
      - auth: { type: password_env, env: AOS_DEVICE_PASSWORD }
    """

    username_env: Optional[str] = None
    username: Optional[str] = None
    auth: Optional[DeviceAuth] = None
    port: int = 22
    tags: List[str] = Field(default_factory=list)
    jump: Optional[str] = None


class ZoneCredentialsConfig(BaseModel):
    """Credentials configuration for a zone or global."""
    username_env: Optional[str] = None
    username: Optional[str] = None
    password_env: Optional[str] = None
    password: Optional[str] = None


class ZoneAuthConfig(BaseModel):
    """Zone-based authentication configuration.
    
    Supports global credentials with per-zone fallback.
    Zone ID is extracted from the second octet of the IP address.
    
    Example:
        zone_auth:
          global:
            username_env: AOS_GLOBAL_USERNAME
            password_env: AOS_GLOBAL_PASSWORD
          zones:
            9:  # Zone ID for 10.9.0.0/16
              username_env: AOS_ZONE9_USERNAME
              password_env: AOS_ZONE9_PASSWORD
    """
    global_: Optional[ZoneCredentialsConfig] = Field(default=None, alias='global')
    zones: Dict[int, ZoneCredentialsConfig] = Field(default_factory=dict)


class InventoryConfig(BaseModel):
    device_defaults: Optional[DeviceDefaults] = None

    # Optional dynamic inventory file used to persist auto-discovered devices.
    # If relative, it is resolved relative to the main config file directory.
    dynamic_inventory_file: Optional[str] = None

    jump_hosts: List[JumpHost] = Field(default_factory=list)
    devices: List[Device] = Field(default_factory=list)


class SSHConfig(BaseModel):
    # Host key verification
    strict_host_key_checking: bool = True
    known_hosts_file: Optional[str] = None  # additional known_hosts file to load

    # Paramiko connect/auth timeouts
    connect_timeout_s: int = 10
    banner_timeout_s: int = 10
    auth_timeout_s: int = 10

    # Command execution control
    default_command_timeout_s: int = 30
    max_output_bytes: int = 200_000  # cap output to avoid exfil / memory blow-ups

    # Optional commands executed before the user command (e.g., disable paging)
    pre_commands: List[str] = Field(default_factory=list)

    # Keepalive
    keepalive_s: Optional[int] = 30


class CommandPolicyConfig(BaseModel):
    # Commands must match at least one allow regex and must match none of the deny regex.
    allow_regex: List[str] = Field(default_factory=lambda: [r"^show\s+.*$", r"^ping\s+.*$", r"^traceroute\s+.*$"])
    deny_regex: List[str] = Field(default_factory=list)

    max_command_length: int = 512
    deny_multiline: bool = True

    # If true, strip ANSI escape sequences from outputs
    strip_ansi: bool = True

    # Output redaction rules: list of {pattern, replacement}
    redactions: List[Dict[str, str]] = Field(default_factory=lambda: [
        # Example patterns; adapt to your environment
        {"pattern": r"(?i)(password\s+)(\S+)", "replacement": r"\1***"},
        {"pattern": r"(?i)(community\s+)(\S+)", "replacement": r"\1***"},
    ])


class TemplatesConfig(BaseModel):
    # Templates for typed diagnostic tools.
    ping: str = "ping {destination}"
    traceroute: str = "traceroute {destination}"


class FactsConfig(BaseModel):
    """Commands used to collect non-sensitive device facts."""

    enabled: bool = True
    show_system: str = "show system"
    show_chassis: str = "show chassis"


class AuthzConfig(BaseModel):
    # Tool -> required scopes (any-of by default, can be configured by your platform too)
    tool_scopes: Dict[str, List[str]] = Field(default_factory=lambda: {
        "aos.devices.list": ["aos:inventory:read"],
        "aos.inventory.autodiscover": ["aos:inventory:discover"],
        "aos.cli.readonly": ["aos:cli:read"],
        "aos.diag.ping": ["aos:diag:ping"],
        "aos.diag.traceroute": ["aos:diag:traceroute"],
    })

    # If true, deny calls when context has no scopes (fail closed).
    require_scopes: bool = True

    # Device authorization enforcement.
    # If true, the request context must include either allowed_device_ids or allowed_tags.
    enforce_device_authorization: bool = True


class AppConfig(BaseModel):
    ssh: SSHConfig = Field(default_factory=SSHConfig)
    inventory: InventoryConfig = Field(default_factory=InventoryConfig)
    command_policy: CommandPolicyConfig = Field(default_factory=CommandPolicyConfig)
    templates: TemplatesConfig = Field(default_factory=TemplatesConfig)
    facts: FactsConfig = Field(default_factory=FactsConfig)
    authz: AuthzConfig = Field(default_factory=AuthzConfig)
    zone_auth: Optional[ZoneAuthConfig] = None


def load_config(path: str) -> AppConfig:
    import yaml

    raw = yaml.safe_load(open(path, "r", encoding="utf-8")) or {}
    try:
        return AppConfig.model_validate(raw)
    except ValidationError as e:
        raise RuntimeError(f"Invalid config file {path}: {e}") from e
