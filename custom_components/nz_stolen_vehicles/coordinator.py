"""Data update coordinator for NZ Stolen Vehicles."""

from __future__ import annotations

import csv
import io
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from aiohttp import ClientTimeout

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_DISTRICT,
    CONF_SCAN_INTERVAL,
    CSV_DISTRICT_BY_ID,
    DEFAULT_DISTRICT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    NATIONAL_DOWNLOAD_URL,
    STORAGE_VERSION,
    USER_AGENT,
    district_label,
    normalize_district_name,
    normalize_plate,
)

_LOGGER = logging.getLogger(__name__)

_CSV_FIELDS = (
    "plate",
    "colour",
    "make",
    "model",
    "year",
    "type",
    "date_stolen",
    "district",
)


@dataclass
class StolenVehiclesData:
    """Parsed stolen-vehicle register."""

    vehicles: list[dict[str, str]]
    by_plate: dict[str, list[dict[str, str]]]
    newest_date: str | None
    district: str
    source_url: str
    last_modified: str | None
    file_unchanged: bool
    national_count: int
    refreshed_at: str


class StolenVehiclesCoordinator(DataUpdateCoordinator[StolenVehiclesData]):
    """Download and cache the Police stolen vehicles CSV."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.entry = entry
        self._store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}"
        )
        self._last_modified: str | None = None
        self._all_vehicles: list[dict[str, str]] = []
        self._store_loaded = False
        hours = entry.options.get(
            CONF_SCAN_INTERVAL,
            entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
        )
        super().__init__(
            hass,
            _LOGGER,
            name="NZ Stolen Vehicles",
            update_interval=timedelta(hours=hours),
            config_entry=entry,
        )

    @property
    def district(self) -> str:
        """Configured district id."""
        return self.entry.options.get(
            CONF_DISTRICT, self.entry.data.get(CONF_DISTRICT, DEFAULT_DISTRICT)
        )

    def lookup(self, plate: str) -> list[dict[str, str]]:
        """Return matching vehicles for a normalised or raw plate."""
        if not self.data:
            return []
        key = normalize_plate(plate)
        if not key:
            return []
        return list(self.data.by_plate.get(key, []))

    async def _async_load_store(self) -> None:
        if self._store_loaded:
            return
        stored = await self._store.async_load()
        self._store_loaded = True
        if not stored:
            return
        self._last_modified = stored.get("last_modified")
        vehicles = stored.get("vehicles")
        if isinstance(vehicles, list):
            self._all_vehicles = vehicles

    async def _async_save_store(self) -> None:
        await self._store.async_save(
            {
                "last_modified": self._last_modified,
                "vehicles": self._all_vehicles,
            }
        )

    async def _async_update_data(self) -> StolenVehiclesData:
        await self._async_load_store()
        session = async_get_clientsession(self.hass)
        headers = {"User-Agent": USER_AGENT, "Accept": "text/csv,*/*"}
        if self._last_modified and self._all_vehicles:
            headers["If-Modified-Since"] = self._last_modified

        try:
            async with session.get(
                NATIONAL_DOWNLOAD_URL,
                headers=headers,
                timeout=ClientTimeout(total=60),
            ) as response:
                if response.status == 304 and self._all_vehicles:
                    _LOGGER.debug(
                        "Police list unchanged since %s, skipping download",
                        self._last_modified,
                    )
                    return self._build_data(file_unchanged=True)

                if response.status == 404:
                    raise UpdateFailed("Police returned no stolen vehicles data")
                if response.status == 304:
                    # Cache missing — fall through to a full GET below.
                    text = None
                    last_modified = self._last_modified
                elif response.status != 200:
                    raise UpdateFailed(
                        f"Police download failed ({response.status}) "
                        f"for {NATIONAL_DOWNLOAD_URL}"
                    )
                else:
                    text = await response.text()
                    last_modified = response.headers.get("Last-Modified")
        except UpdateFailed:
            raise
        except Exception as err:
            raise UpdateFailed(f"Could not download stolen vehicles list: {err}") from err

        if text is None:
            text, last_modified = await self._async_download_full(session)

        vehicles = _parse_csv(text)
        if not vehicles:
            raise UpdateFailed("Police CSV was empty or could not be parsed")

        self._all_vehicles = vehicles
        self._last_modified = last_modified
        await self._async_save_store()
        _LOGGER.debug(
            "Downloaded %s stolen vehicles (file last-modified %s)",
            len(vehicles),
            last_modified,
        )
        return self._build_data(file_unchanged=False)

    async def _async_download_full(self, session) -> tuple[str, str | None]:
        """Download the national CSV with no conditional headers."""
        async with session.get(
            NATIONAL_DOWNLOAD_URL,
            headers={"User-Agent": USER_AGENT, "Accept": "text/csv,*/*"},
            timeout=ClientTimeout(total=60),
        ) as response:
            if response.status != 200:
                raise UpdateFailed(
                    f"Police download failed ({response.status}) "
                    f"for {NATIONAL_DOWNLOAD_URL}"
                )
            return await response.text(), response.headers.get("Last-Modified")

    def _build_data(self, file_unchanged: bool) -> StolenVehiclesData:
        district = self.district
        vehicles, by_plate, newest = _filter_vehicles(self._all_vehicles, district)
        return StolenVehiclesData(
            vehicles=vehicles,
            by_plate=by_plate,
            newest_date=newest,
            district=district,
            source_url=NATIONAL_DOWNLOAD_URL,
            last_modified=self._last_modified,
            file_unchanged=file_unchanged,
            national_count=len(self._all_vehicles),
            refreshed_at=datetime.now(timezone.utc).isoformat(),
        )


def _parse_csv(text: str) -> list[dict[str, str]]:
    """Parse the headerless Police CSV into vehicle dicts."""
    vehicles: list[dict[str, str]] = []
    reader = csv.reader(io.StringIO(text))
    for row in reader:
        if len(row) < 8:
            continue
        plate = row[0].strip()
        if not normalize_plate(plate):
            continue
        vehicles.append(
            {
                _CSV_FIELDS[0]: plate,
                _CSV_FIELDS[1]: row[1].strip(),
                _CSV_FIELDS[2]: row[2].strip(),
                _CSV_FIELDS[3]: row[3].strip(),
                _CSV_FIELDS[4]: row[4].strip(),
                _CSV_FIELDS[5]: row[5].strip(),
                _CSV_FIELDS[6]: row[6].strip(),
                _CSV_FIELDS[7]: row[7].strip(),
            }
        )
    return vehicles


def _filter_vehicles(
    vehicles: list[dict[str, str]], district: str
) -> tuple[list[dict[str, str]], dict[str, list[dict[str, str]]], str | None]:
    """Filter cached national rows down to the configured area."""
    if district == "all":
        filtered = vehicles
    else:
        wanted = normalize_district_name(
            CSV_DISTRICT_BY_ID.get(district, district_label(district))
        )
        filtered = [
            vehicle
            for vehicle in vehicles
            if normalize_district_name(vehicle.get("district", "")) == wanted
        ]

    by_plate: dict[str, list[dict[str, str]]] = {}
    newest: str | None = None
    for vehicle in filtered:
        key = normalize_plate(vehicle["plate"])
        by_plate.setdefault(key, []).append(vehicle)
        date_stolen = vehicle.get("date_stolen", "")
        if date_stolen and (newest is None or date_stolen > newest):
            newest = date_stolen
    return filtered, by_plate, newest
