from __future__ import annotations

import os
import socket
import time
import threading
from dataclasses import dataclass
from typing import Optional, Tuple

import paramiko

from .config import (
    AuthPasswordEnv,
    AuthPasswordInline,
    AuthPrivateKeyFile,
    Device,
    DeviceAuth,
    JumpHost,
    SSHConfig,
)

# Lock for thread-safe known_hosts file operations
_known_hosts_lock = threading.Lock()


class SSHExecutionError(RuntimeError):
    pass


def _update_known_hosts_file(filepath: str, hostname: str, key: paramiko.PKey) -> None:
    """Thread-safe update of known_hosts file - adds or replaces a single host key.
    
    Args:
        filepath: Path to known_hosts file
        hostname: Hostname or IP address
        key: SSH host key to save
    """
    key_type = key.get_name()
    key_base64 = key.get_base64()
    new_line = f"{hostname} {key_type} {key_base64}\n"
    
    with _known_hosts_lock:
        lines = []
        
        # Read existing file if it exists
        if os.path.exists(filepath):
            try:
                with open(filepath, 'r') as f:
                    lines = f.readlines()
            except Exception:
                lines = []
        
        # Find and replace existing entry for this hostname, or append
        found = False
        new_lines = []
        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith('#'):
                new_lines.append(line)
                continue
            
            parts = stripped.split()
            if len(parts) >= 2:
                existing_host = parts[0]
                # Handle hashed hostnames and comma-separated hostnames
                hostnames = existing_host.split(',')
                if hostname in hostnames or existing_host == hostname:
                    # Replace this line with new key
                    new_lines.append(new_line)
                    found = True
                    continue
            
            new_lines.append(line)
        
        # If not found, append the new key
        if not found:
            new_lines.append(new_line)
        
        # Write back atomically
        try:
            with open(filepath, 'w') as f:
                f.writelines(new_lines)
        except Exception as e:
            print(f"Warning: Could not save host key to {filepath}: {e}")


class AutoAddAndSavePolicy(paramiko.MissingHostKeyPolicy):
    """Policy that auto-adds missing host keys and saves them to known_hosts file.
    
    Unlike paramiko's default save_host_keys(), this implementation:
    - Only updates the specific host entry (doesn't overwrite the entire file)
    - Is thread-safe for concurrent connections
    - Preserves comments and other entries in the file
    """
    
    def __init__(self, known_hosts_file: Optional[str] = None):
        self.known_hosts_file = known_hosts_file
    
    def missing_host_key(self, client, hostname, key):
        # Add the key to the client's in-memory known_hosts
        client._host_keys.add(hostname, key.get_name(), key)
        
        # Save to file if path is provided
        if self.known_hosts_file:
            _update_known_hosts_file(self.known_hosts_file, hostname, key)


@dataclass(frozen=True)
class SSHResult:
    stdout: str
    stderr: str
    exit_status: Optional[int]
    duration_ms: int
    truncated: bool = False


def _build_client(cfg: SSHConfig) -> paramiko.SSHClient:
    client = paramiko.SSHClient()
    if cfg.strict_host_key_checking:
        client.load_system_host_keys()
        if cfg.known_hosts_file:
            try:
                client.load_host_keys(cfg.known_hosts_file)
            except FileNotFoundError as e:
                raise RuntimeError(f"known_hosts_file not found: {cfg.known_hosts_file}") from e
        client.set_missing_host_key_policy(paramiko.RejectPolicy())
    else:
        # Use custom policy that saves keys to known_hosts file
        client.set_missing_host_key_policy(AutoAddAndSavePolicy(cfg.known_hosts_file))
    return client


def _resolve_password(auth: AuthPasswordEnv | AuthPasswordInline) -> str:
    if isinstance(auth, AuthPasswordEnv):
        value = os.environ.get(auth.env)
        if not value:
            raise RuntimeError(f"Missing required environment variable: {auth.env}")
        return value
    return auth.password.get_secret_value()


def _connect(
    cfg: SSHConfig,
    host: str,
    port: int,
    username: str,
    auth: DeviceAuth,
    *,
    sock_obj=None,
) -> paramiko.SSHClient:
    client = _build_client(cfg)

    password: Optional[str] = None
    key_filename: Optional[str] = None
    passphrase: Optional[str] = None

    if isinstance(auth, (AuthPasswordEnv, AuthPasswordInline)):
        password = _resolve_password(auth)
    elif isinstance(auth, AuthPrivateKeyFile):
        key_filename = auth.private_key_file
        if auth.passphrase_env:
            passphrase = os.environ.get(auth.passphrase_env)
            if passphrase is None:
                raise RuntimeError(f"Missing required environment variable: {auth.passphrase_env}")
    else:
        raise RuntimeError(f"Unsupported auth type: {type(auth)}")

    client.connect(
        hostname=host,
        port=port,
        username=username,
        password=password,
        key_filename=key_filename,
        passphrase=passphrase,
        timeout=cfg.connect_timeout_s,
        banner_timeout=cfg.banner_timeout_s,
        auth_timeout=cfg.auth_timeout_s,
        sock=sock_obj,
        look_for_keys=False,
        allow_agent=False,
    )

    if cfg.keepalive_s is not None:
        transport = client.get_transport()
        if transport is not None:
            transport.set_keepalive(cfg.keepalive_s)

    return client


def _open_jump_channel(
    jump_client: paramiko.SSHClient,
    dest_host: str,
    dest_port: int,
) -> paramiko.Channel:
    transport = jump_client.get_transport()
    if transport is None:
        raise SSHExecutionError("Jump host transport not available")

    dest_addr: Tuple[str, int] = (dest_host, dest_port)
    local_addr: Tuple[str, int] = ("127.0.0.1", 0)
    return transport.open_channel("direct-tcpip", dest_addr, local_addr)


def _read_limited(stream, limit: int) -> tuple[str, bool]:
    # stream is a paramiko channel file.
    data = stream.read(limit + 1)
    if not isinstance(data, (bytes, bytearray)):
        # paramiko returns bytes; but keep defensive
        data_bytes = str(data).encode("utf-8", errors="replace")
    else:
        data_bytes = bytes(data)
    truncated = len(data_bytes) > limit
    data_bytes = data_bytes[:limit]
    return data_bytes.decode("utf-8", errors="replace"), truncated


class SSHRunner:
    def __init__(
        self,
        cfg: SSHConfig,
        *,
        jump_hosts: dict[str, JumpHost],
        default_device_username: Optional[str] = None,
        default_device_auth: Optional[DeviceAuth] = None,
    ):
        self._cfg = cfg
        self._jump_hosts = jump_hosts
        self._default_device_username = default_device_username
        self._default_device_auth = default_device_auth

    def _resolve_username(self, device: Device, zone_resolver: Optional[object] = None) -> str:
        """Resolve SSH username for a device.

        Order of precedence:
        1) device.username
        2) zone_resolver global/zone credentials (if available)
        3) default_device_username passed to SSHRunner
        4) environment variable AOS_DEVICE_USERNAME
        """
        if device.username:
            return device.username
        
        # Try zone resolver if available (uses global first, then zone)
        if zone_resolver is not None:
            try:
                creds = zone_resolver.get_primary_credentials(device.host)
                if creds and creds[0]:  # creds is (username, password) tuple
                    return creds[0]
            except Exception:
                pass
        
        username = self._default_device_username or os.environ.get("AOS_DEVICE_USERNAME")
        if not username:
            raise SSHExecutionError(
                f"Missing SSH username for device '{device.id}'. "
                "Set device.username in the inventory or export AOS_DEVICE_USERNAME."
            )
        return username

    def _resolve_auth(self, device: Device, zone_resolver: Optional[object] = None) -> DeviceAuth:
        """Resolve SSH auth method for a device.

        Order of precedence:
        1) device.auth
        2) zone_resolver global/zone credentials (if available)
        3) default_device_auth passed to SSHRunner
        4) password from env var AOS_DEVICE_PASSWORD (AuthPasswordEnv)
        """
        if device.auth is not None:
            return device.auth

        # Try zone resolver if available (uses global first, then zone)
        if zone_resolver is not None:
            try:
                creds = zone_resolver.get_primary_credentials(device.host)
                if creds and creds[1]:  # creds is (username, password) tuple
                    return AuthPasswordInline(type="password_inline", password=creds[1])
            except Exception:
                pass

        if self._default_device_auth is not None:
            return self._default_device_auth

        # Default: password stored in env var.
        if not os.environ.get("AOS_DEVICE_PASSWORD"):
            raise SSHExecutionError(
                f"Missing SSH password for device '{device.id}'. "
                "Set device.auth in the inventory or export AOS_DEVICE_PASSWORD."
            )
        return AuthPasswordEnv(type="password_env", env="AOS_DEVICE_PASSWORD")

    def run(self, device: Device, command: str, timeout_s: Optional[int] = None, zone_resolver: Optional[object] = None) -> SSHResult:
        start = time.time()
        truncated_any = False
        timeout = timeout_s if timeout_s is not None else self._cfg.default_command_timeout_s
        
        # Resolve username and password using zone_resolver if available
        username = self._resolve_username(device, zone_resolver)
        auth = self._resolve_auth(device, zone_resolver)

        jump_client: Optional[paramiko.SSHClient] = None
        client: Optional[paramiko.SSHClient] = None

        try:
            sock_obj = None
            if device.jump:
                jump = self._jump_hosts.get(device.jump)
                if jump is None:
                    raise SSHExecutionError(f"Unknown jump host: {device.jump}")
                jump_client = _connect(
                    self._cfg,
                    jump.host,
                    jump.port,
                    jump.username,
                    jump.auth,
                    sock_obj=None,
                )
                sock_obj = _open_jump_channel(jump_client, device.host, device.port)

            client = _connect(
                self._cfg,
                device.host,
                device.port,
                username,
                auth,
                sock_obj=sock_obj,
            )

            # Pre-commands (e.g., disable paging)
            for pre in self._cfg.pre_commands:
                if pre.strip():
                    client.exec_command(pre.strip(), timeout=timeout)

            stdin, stdout, stderr = client.exec_command(command, timeout=timeout)

            out, truncated_out = _read_limited(stdout, self._cfg.max_output_bytes)
            err, truncated_err = _read_limited(stderr, self._cfg.max_output_bytes)
            truncated_any = truncated_out or truncated_err

            exit_status = None
            try:
                exit_status = stdout.channel.recv_exit_status()
            except Exception:
                exit_status = None

            duration_ms = int((time.time() - start) * 1000)
            return SSHResult(
                stdout=out,
                stderr=err,
                exit_status=exit_status,
                duration_ms=duration_ms,
                truncated=truncated_any,
            )
        except (paramiko.SSHException, socket.timeout, OSError) as e:
            raise SSHExecutionError(str(e)) from e
        finally:
            try:
                if client:
                    client.close()
            finally:
                if jump_client:
                    jump_client.close()
