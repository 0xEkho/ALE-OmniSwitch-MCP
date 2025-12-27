from __future__ import annotations

import re
from typing import Any, Dict, Optional

from .ssh_runner import SSHRunner
from .config import Device


_RE_KV_COLON = re.compile(r"^\s*([A-Za-z0-9 &/_-]+?)\s*:\s*(.*?)\s*,?\s*$")
_RE_VERSION = re.compile(r"\b\d+\.\d+\.\d+\.R\d+\b")


def parse_show_system(output: str) -> Dict[str, Any]:
    """Parse 'show system' output (best effort).

    The AOS CLI reference guide documents that 'show system' displays basic system information and
    provides examples containing: Description, Object ID, Up Time, Contact, Name, Location, Services,
    Date & Time.
    """
    facts: Dict[str, Any] = {}
    lines = output.splitlines()

    # Only parse the "System:" block to avoid matching unrelated sections.
    in_system = False
    for raw in lines:
        line = raw.strip("\r\n")
        if line.strip().lower() == "system:":
            in_system = True
            continue
        if in_system and line and not line.startswith(" ") and not line.startswith("\t"):
            # next top-level section (e.g., "Flash Space:")
            break

        if not in_system:
            continue

        m = _RE_KV_COLON.match(line)
        if not m:
            continue
        key = m.group(1).strip().lower()
        value = m.group(2).strip().strip('"')

        if key == "description":
            facts["system_description"] = value
            # Extract a software version token if present inside the description.
            mv = _RE_VERSION.search(value)
            if mv:
                facts["software_version"] = mv.group(0)
        elif key == "object id":
            facts["snmp_object_id"] = value
        elif key == "up time":
            facts["uptime"] = value
        elif key == "contact":
            facts["contact"] = value
        elif key == "name":
            facts["system_name"] = value
        elif key == "location":
            facts["location"] = value
        elif key == "services":
            facts["services"] = value
        elif key == "date & time":
            facts["date_time"] = value

    return facts


def parse_show_chassis(output: str) -> Dict[str, Any]:
    """Parse 'show chassis' output (best effort).

    CLI reference examples contain fields such as Model Name, Serial Number, Part Number,
    Hardware Revision, Manufacture Date, MAC Address.
    """
    facts: Dict[str, Any] = {}
    for raw in output.splitlines():
        line = raw.strip("\r\n")
        m = _RE_KV_COLON.match(line)
        if not m:
            continue
        key = m.group(1).strip().lower()
        value = m.group(2).strip().strip('"')

        if key == "model name":
            facts["model"] = value
        elif key == "serial number":
            facts["serial_number"] = value
        elif key == "part number":
            facts["part_number"] = value
        elif key == "hardware revision":
            facts["hardware_revision"] = value
        elif key == "manufacture date":
            facts["manufacture_date"] = value
        elif key == "mac address":
            facts["base_mac"] = value

    return facts


def parse_show_hardware_info(output: str) -> Dict[str, Any]:
    """Parse 'show hardware-info' output (best effort)."""
    hw: Dict[str, Any] = {}
    for raw in output.splitlines():
        line = raw.strip("\r\n")
        m = _RE_KV_COLON.match(line)
        if not m:
            continue
        key = m.group(1).strip().lower()
        value = m.group(2).strip().strip('"')

        if key == "cpu manufacturer":
            hw["cpu_manufacturer"] = value
        elif key == "cpu model":
            hw["cpu_model"] = value
        elif key == "flash size":
            hw["flash_size"] = value
        elif key == "ram size":
            hw["ram_size"] = value
        elif key == "fpga version":
            hw["fpga_version"] = value
        elif key == "bootrom version":
            hw["bootrom_version"] = value
        elif key == "miniboot version":
            hw["miniboot_version"] = value

    return {"hardware": hw} if hw else {}


def collect_device_facts(runner: SSHRunner, device: Device) -> Dict[str, Any]:
    """Collect facts from a device using read-only CLI commands.

    Commands executed:
    - show system
    - show chassis
    - show hardware-info
    """
    facts: Dict[str, Any] = {}

    sys_out = runner.run(device, "show system").stdout
    facts.update(parse_show_system(sys_out))

    chassis_out = runner.run(device, "show chassis").stdout
    facts.update(parse_show_chassis(chassis_out))

    # Not all platforms expose exactly the same fields; best effort.
    try:
        hw_out = runner.run(device, "show hardware-info").stdout
        facts.update(parse_show_hardware_info(hw_out))
    except Exception:
        pass

    return facts


def facts_summary(facts: Optional[Dict[str, Any]]) -> str:
    """Return a short, safe one-line summary of collected facts.

    Used for logs and discovery output. Must never raise.
    """
    try:
        if not facts:
            return "no-facts"

        parts = []
        for key in (
            "system_name",
            "model",
            "serial_number",
            "software_version",
            "uptime",
        ):
            val = facts.get(key) if isinstance(facts, dict) else None
            if val:
                parts.append(f"{key}={val}")
        return " ".join(parts) if parts else "facts-present"
    except Exception:
        return "facts-summary-error"
