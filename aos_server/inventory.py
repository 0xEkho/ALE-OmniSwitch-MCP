from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from typing import Dict, List, Optional

from .config import Device, InventoryConfig, JumpHost


logger = logging.getLogger("aos_server.inventory")


@dataclass(frozen=True)
class InventorySnapshot:
    """Immutable view of the current inventory.

    Intended for returning data to callers without exposing internal locks.
    """

    devices_by_id: Dict[str, Device]
    jumps_by_name: Dict[str, JumpHost]
    device_id_by_host: Dict[str, str]


class InventoryStore:
    """Thread-safe inventory store.

    This store is mutable on purpose to support auto-discovery that can add devices at runtime.

    Duplicate handling (requested):
    - No fuzzy matching / heuristics.
    - Exact duplicates (same device_id or same host) are logged at ERROR.
    """

    def __init__(self, cfg: InventoryConfig):
        self._lock = threading.RLock()

        self._devices_by_id: Dict[str, Device] = {d.id: d for d in cfg.devices}
        self._device_id_by_host: Dict[str, str] = {d.host: d.id for d in cfg.devices if d.host}
        self._jumps_by_name: Dict[str, JumpHost] = {j.name: j for j in cfg.jump_hosts}

    @classmethod
    def from_config(cls, cfg: InventoryConfig) -> "InventoryStore":
        return cls(cfg)

    def snapshot(self) -> InventorySnapshot:
        with self._lock:
            return InventorySnapshot(
                devices_by_id=dict(self._devices_by_id),
                jumps_by_name=dict(self._jumps_by_name),
                device_id_by_host=dict(self._device_id_by_host),
            )

    def get_device(self, device_id: str) -> Device:
        with self._lock:
            if device_id not in self._devices_by_id:
                raise KeyError(f"Unknown device_id: {device_id}")
            return self._devices_by_id[device_id]

    def get_jump(self, name: str) -> JumpHost:
        with self._lock:
            if name not in self._jumps_by_name:
                raise KeyError(f"Unknown jump host: {name}")
            return self._jumps_by_name[name]

    def list_devices(self, tags: Optional[List[str]] = None) -> List[Device]:
        with self._lock:
            devices = list(self._devices_by_id.values())
        if not tags:
            return devices
        tag_set = set(tags)
        return [d for d in devices if tag_set.intersection(set(d.tags))]

    def add_device_if_absent(self, device: Device) -> bool:
        """Add a device if it does not already exist.

        Duplicate policy:
        - If device_id already exists: do not overwrite; log error; return False.
        - If host already exists under another device_id: do not add; log error; return False.
        - If name duplicates an existing name on another host: log error but still add.
        """
        with self._lock:
            if device.id in self._devices_by_id:
                logger.error(
                    "inventory_duplicate_device_id",
                    extra={"device_id": device.id, "host": device.host},
                )
                return False

            if device.host and device.host in self._device_id_by_host:
                existing_id = self._device_id_by_host[device.host]
                logger.error(
                    "inventory_duplicate_host",
                    extra={
                        "host": device.host,
                        "existing_device_id": existing_id,
                        "new_device_id": device.id,
                    },
                )
                return False

            if device.name:
                for d in self._devices_by_id.values():
                    if d.name and d.name.strip().lower() == device.name.strip().lower() and d.host != device.host:
                        logger.error(
                            "inventory_duplicate_name",
                            extra={
                                "name": device.name,
                                "existing_device_id": d.id,
                                "existing_host": d.host,
                                "new_device_id": device.id,
                                "new_host": device.host,
                            },
                        )
                        break

            self._devices_by_id[device.id] = device
            if device.host:
                self._device_id_by_host[device.host] = device.id
            return True

    def update_device_facts(self, device_id: str, facts: Dict[str, object]) -> None:
        with self._lock:
            if device_id not in self._devices_by_id:
                raise KeyError(f"Unknown device_id: {device_id}")
            d = self._devices_by_id[device_id]
            merged = dict(d.facts or {})
            merged.update(facts)
            self._devices_by_id[device_id] = d.model_copy(update={"facts": merged})
