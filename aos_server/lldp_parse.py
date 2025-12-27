from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional


@dataclass(frozen=True)
class LldpNeighbor:
    local_port: str
    chassis_id: Optional[str] = None
    port_id: Optional[str] = None
    port_description: Optional[str] = None
    system_name: Optional[str] = None
    system_description: Optional[str] = None
    management_ip: Optional[str] = None


# Accept both formats:
# - AOS 5:  "Remote LLDP Agents on Local Slot/Port: 2/47,"
# - AOS 8+: "Remote LLDP nearest-bridge Agents on Local Port 1/1/25:"
_RE_PORT_HEADER = re.compile(
    r"^Remote LLDP(?:\s+\S+)*\s+Agents on Local\s+(?:Slot/Port:\s*|Port\s+)"
    r"([0-9]+(?:/[0-9]+)+)\s*[:,]?\s*$"
)
_RE_CHASSIS_PORT = re.compile(r"^\s*Chassis\s+([^,]+),\s*Port\s+(.+):\s*$")
_RE_KV = re.compile(r"^\s*([A-Za-z0-9 /_-]+?)\s*=\s*(.*?),?\s*$")
_RE_IPv4 = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")


def parse_show_lldp_remote_system(output: str) -> List[LldpNeighbor]:
    """
    Parse output of 'show lldp remote-system' (AOS syntax verified in AOS 5 CLI reference guide).
    The guide shows a per-local-port block starting with:
      'Remote LLDP Agents on Local Slot/Port: 2/47,'
    followed by key/value lines such as 'Chassis ID = 00:d0:...,'
    """
    neighbors: List[LldpNeighbor] = []
    current: Optional[LldpNeighbor] = None

    for raw_line in output.splitlines():
        line = raw_line.strip("\r\n")

        m = _RE_PORT_HEADER.match(line.strip())
        if m:
            # commit previous
            if current is not None:
                neighbors.append(current)
            current = LldpNeighbor(local_port=m.group(1))
            continue

        if current is None:
            continue

        # AOS 8+ blocks contain a line like:
        # "Chassis 78:24:..., Port 1016:"
        m = _RE_CHASSIS_PORT.match(line)
        if m:
            current = LldpNeighbor(**{**current.__dict__, "chassis_id": m.group(1).strip(), "port_id": m.group(2).strip()})
            continue

        m = _RE_KV.match(line)
        if not m:
            continue

        # Normalize whitespace in keys (multiple spaces -> single space)
        key = re.sub(r"\s+", " ", m.group(1).strip()).lower()
        value = m.group(2).strip().strip('"')
        if value == "(null)":
            value = ""

        # Normalize keys that appear in the CLI guide example.
        if key.startswith("chassis id") and "subtype" not in key:
            current = LldpNeighbor(**{**current.__dict__, "chassis_id": value})
        elif key.startswith("port id") and "subtype" not in key:
            current = LldpNeighbor(**{**current.__dict__, "port_id": value})
        elif key.startswith("port description"):
            current = LldpNeighbor(**{**current.__dict__, "port_description": value or None})
        elif key.startswith("system name"):
            current = LldpNeighbor(**{**current.__dict__, "system_name": value or None})
        elif key.startswith("system description"):
            current = LldpNeighbor(**{**current.__dict__, "system_description": value or None})
        elif "management ip address" in key or "management address" in key:
            ip = _RE_IPv4.search(value)
            if ip:
                current = LldpNeighbor(**{**current.__dict__, "management_ip": ip.group(0)})

    if current is not None:
        neighbors.append(current)

    return neighbors


def parse_show_lldp_local_management_address(output: str) -> Optional[str]:
    """
    Parse 'show lldp local-management-address' output to obtain local management IPv4 address.

    Example in AOS 5 CLI reference guide:
      Local LLDP Agent Management Address:
        Management Address Type = 1 (IPv4),
        Management IP Address = 10.255.11.100
    """
    for raw_line in output.splitlines():
        m = re.search(r"Management IP Address\s*=\s*(" + _RE_IPv4.pattern + r")", raw_line)
        if m:
            return m.group(1)
    return None
