from __future__ import annotations

import logging
import re
import socket
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple

from .config import Device
from .facts import collect_device_facts, facts_summary
from .lldp_parse import parse_show_lldp_local_management_address, parse_show_lldp_remote_system
from .policy import CompiledCommandPolicy, sanitize_command
from .ssh_runner import SSHExecutionError, SSHRunner


logger = logging.getLogger("aos_server.autodiscover")


DEFAULT_VENDOR_REGEX = r"(?i)(omniswitch|alcatel|alcatel-lucent|\bALE\b)"


@dataclass(frozen=True)
class DiscoveredDevice:
    host: str
    system_name: Optional[str] = None
    system_description: Optional[str] = None
    via_device_id: Optional[str] = None
    via_local_port: Optional[str] = None
    chassis_id: Optional[str] = None
    port_id: Optional[str] = None
    port_description: Optional[str] = None
    management_ip: Optional[str] = None


def _is_vendor_match(system_name: Optional[str], system_desc: Optional[str], port_desc: Optional[str], vendor_re: re.Pattern[str]) -> bool:
    hay = " ".join([(system_name or ""), (system_desc or ""), (port_desc or "")])
    return bool(vendor_re.search(hay))


def _resolve_host_from_system_name(system_name: str, dns_suffixes: List[str]) -> Optional[str]:
    s = system_name.strip()
    if not s:
        return None

    candidates: List[str] = []
    if "." in s:
        candidates.append(s)
    for suf in dns_suffixes:
        suf2 = suf.strip().lstrip(".")
        if suf2:
            candidates.append(f"{s}.{suf2}")
    candidates.append(s)

    for c in candidates:
        try:
            socket.gethostbyname(c)
            return c
        except OSError:
            continue
    return None


def _safe_id_fragment(value: str) -> str:
    v = value.strip().lower()
    v = re.sub(r"[^a-z0-9]+", "-", v)
    return v.strip("-")


def _auto_device_id(host: str) -> str:
    return f"auto:host:{_safe_id_fragment(host)}"


def autodiscover_alcatel_switches(
    *,
    seed: Device,
    runner: SSHRunner,
    policy: CompiledCommandPolicy,
    dns_suffixes: Optional[List[str]] = None,
    max_depth: int = 10,
    max_devices: int = 200,
    vendor_regex: Optional[str] = None,
    collect_facts: bool = True,
) -> Tuple[List[Device], List[DiscoveredDevice]]:
    """Auto-discover Alcatel/ALE switches by crawling LLDP.

    Returns:
      - created_devices: list of Device objects (including newly discovered ones) to be inserted by caller.
      - discovered: lightweight discovery edges for reporting.

    Notes:
      - No dedup heuristics: duplicates are handled by the inventory store (caller) and should be logged there.
      - Credentials are resolved by SSHRunner (global env vars or per-device overrides).
    """

    dns_suffixes = dns_suffixes or []
    vend_re = re.compile(vendor_regex or DEFAULT_VENDOR_REGEX)

    # We keep a local set by host to avoid redundant SSH attempts.
    seen_hosts: Set[str] = set()
    seen_device_ids: Set[str] = set()

    created: List[Device] = []
    discovered_edges: List[DiscoveredDevice] = []

    # BFS over devices we can actually reach.
    queue: List[Tuple[Device, int]] = [(seed, 0)]

    def _enqueue(dev: Device, depth: int) -> None:
        if depth > max_depth:
            return
        if len(seen_device_ids) >= max_devices:
            return
        if dev.id in seen_device_ids:
            return
        seen_device_ids.add(dev.id)
        queue.append((dev, depth))

    # Seed
    if seed.host:
        seen_hosts.add(seed.host)
    _enqueue(seed, 0)

    while queue and len(seen_device_ids) <= max_devices:
        device, depth = queue.pop(0)

        # Collect facts (optional)
        if collect_facts:
            try:
                facts = collect_device_facts(runner, device)
                # Store in the created list too (caller may use this to update inventory facts).
                device = device.model_copy(update={"facts": facts})
                logger.info(
                    "facts_collected",
                    extra={"device_id": device.id, "host": device.host, "facts": facts_summary(facts)},
                )
            except Exception as e:
                logger.warning(
                    "facts_collection_failed",
                    extra={"device_id": device.id, "host": device.host, "error": str(e)},
                )

        # Track the device object (so caller can add/update)
        created.append(device)

        # Local management address (best effort; not required)
        try:
            cmd = sanitize_command("show lldp local-management-address", policy)
            res = runner.run(device, cmd)
            mgmt_ip = parse_show_lldp_local_management_address(res.stdout)
            if mgmt_ip and isinstance(device.facts, dict):
                device.facts.setdefault("lldp", {})["local_management_ip"] = mgmt_ip
        except Exception:
            pass

        # LLDP neighbors
        try:
            cmd = sanitize_command("show lldp remote-system", policy)
            res = runner.run(device, cmd)
            neighbors = parse_show_lldp_remote_system(res.stdout)
        except SSHExecutionError as e:
            logger.warning(
                "autodiscover_device_ssh_error",
                extra={"device_id": device.id, "host": device.host, "error": str(e)},
            )
            continue
        except Exception as e:
            logger.warning(
                "autodiscover_device_error",
                extra={"device_id": device.id, "host": device.host, "error": str(e)},
            )
            continue

        for nei in neighbors:
            if not _is_vendor_match(nei.system_name, nei.system_description, nei.port_description, vend_re):
                continue

            host: Optional[str] = None
            if nei.management_ip:
                host = nei.management_ip
            elif nei.system_name:
                host = _resolve_host_from_system_name(nei.system_name, dns_suffixes)

            if not host:
                logger.warning(
                    "autodiscover_neighbor_unresolvable",
                    extra={
                        "via_device_id": device.id,
                        "via_local_port": nei.local_port,
                        "system_name": nei.system_name,
                    },
                )
                continue

            discovered_edges.append(
                DiscoveredDevice(
                    host=host,
                    system_name=nei.system_name,
                    system_description=nei.system_description,
                    via_device_id=device.id,
                    via_local_port=nei.local_port,
                    chassis_id=nei.chassis_id,
                    port_id=nei.port_id,
                    port_description=nei.port_description,
                    management_ip=nei.management_ip,
                )
            )

            if host in seen_hosts:
                continue
            seen_hosts.add(host)

            new_dev = Device(
                id=_auto_device_id(host),
                host=host,
                port=22,
                name=nei.system_name,
                tags=[],
                jump=device.jump,
            )

            _enqueue(new_dev, depth + 1)

    # Return: created includes seed and any intermediate objects. Caller can decide what to do.
    # For inventory insertion, only return devices that have a host (all should).
    created_unique: Dict[str, Device] = {}
    for d in created:
        # Keep last occurrence (may have facts).
        created_unique[d.id] = d
    return list(created_unique.values()), discovered_edges
