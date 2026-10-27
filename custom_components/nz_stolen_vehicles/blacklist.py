"""Local plate blacklist for NZ Stolen Vehicles."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import BLACKLIST_STORAGE_KEY, SOURCE_BLACKLIST, STORAGE_VERSION, normalize_plate

_LOGGER = logging.getLogger(__name__)


class PlateBlacklist:
    """Persisted user blacklist of plates (domain-wide, not per district)."""

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self._store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, BLACKLIST_STORAGE_KEY
        )
        self._plates: dict[str, dict[str, str]] = {}
        self._loaded = False

    @property
    def count(self) -> int:
        """Number of blacklisted plates."""
        return len(self._plates)

    async def async_load(self) -> None:
        """Load blacklist from storage."""
        if self._loaded:
            return
        stored = await self._store.async_load()
        self._loaded = True
        if not stored:
            return
        plates = stored.get("plates")
        if isinstance(plates, dict):
            self._plates = {
                key: value
                for key, value in plates.items()
                if isinstance(key, str) and isinstance(value, dict)
            }

    async def _async_save(self) -> None:
        await self._store.async_save({"plates": self._plates})

    def lookup(self, plate: str) -> list[dict[str, str]]:
        """Return blacklist matches for a plate."""
        key = normalize_plate(plate)
        if not key or key not in self._plates:
            return []
        entry = self._plates[key]
        match = {
            "plate": entry.get("plate", key),
            "colour": "",
            "make": "",
            "model": "",
            "year": "",
            "type": "",
            "date_stolen": entry.get("added_at", ""),
            "district": "",
            "source": SOURCE_BLACKLIST,
            "reason": entry.get("reason", ""),
        }
        return [match]

    async def async_add(self, plate: str, reason: str = "") -> dict[str, Any]:
        """Add or update a blacklisted plate. Reason is optional."""
        await self.async_load()
        key = normalize_plate(plate)
        if not key:
            raise ValueError("Plate is empty after normalisation")

        existing = key in self._plates
        entry = {
            "plate": key,
            "reason": (reason or "").strip(),
            "added_at": datetime.now(timezone.utc).isoformat(),
        }
        self._plates[key] = entry
        await self._async_save()
        _LOGGER.info(
            "%s blacklist plate %s%s",
            "Updated" if existing else "Added",
            key,
            f" ({entry['reason']})" if entry["reason"] else "",
        )
        return {
            "ok": True,
            "updated": existing,
            "plate": plate,
            "normalized_plate": key,
            "reason": entry["reason"],
            "blacklist_count": self.count,
        }

    async def async_remove(self, plate: str) -> dict[str, Any]:
        """Remove a plate from the blacklist."""
        await self.async_load()
        key = normalize_plate(plate)
        removed = self._plates.pop(key, None) is not None
        if removed:
            await self._async_save()
            _LOGGER.info("Removed blacklist plate %s", key)
        return {
            "ok": True,
            "removed": removed,
            "plate": plate,
            "normalized_plate": key,
            "blacklist_count": self.count,
        }

    def as_list(self) -> list[dict[str, str]]:
        """Return all blacklist entries."""
        return [
            {
                "plate": entry.get("plate", key),
                "reason": entry.get("reason", ""),
                "added_at": entry.get("added_at", ""),
            }
            for key, entry in sorted(self._plates.items())
        ]
