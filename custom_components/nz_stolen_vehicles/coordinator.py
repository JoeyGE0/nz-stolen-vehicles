"""Data update coordinator for NZ Stolen Vehicles."""

from __future__ import annotations

import csv
import io
import logging
from dataclasses import dataclass
from datetime import timedelta

from aiohttp import ClientTimeout

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_DISTRICT,
    CONF_SCAN_INTERVAL,
    DEFAULT_DISTRICT,
    DEFAULT_SCAN_INTERVAL,
    USER_AGENT,
    district_label,
    download_url,
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


class StolenVehiclesCoordinator(DataUpdateCoordinator[StolenVehiclesData]):
    """Download and cache the Police stolen vehicles CSV."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.entry = entry
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

    async def _async_update_data(self) -> StolenVehiclesData:
        district = self.district
        url = download_url(district)
        session = async_get_clientsession(self.hass)

        try:
            async with session.get(
                url,
                headers={"User-Agent": USER_AGENT, "Accept": "text/csv,*/*"},
                timeout=ClientTimeout(total=60),
            ) as response:
                if response.status == 404:
                    raise UpdateFailed(
                        f"Police returned no data for {district_label(district)}"
                    )
                if response.status != 200:
                    raise UpdateFailed(
                        f"Police download failed ({response.status}) for {url}"
                    )
                text = await response.text()
        except UpdateFailed:
            raise
        except Exception as err:
            raise UpdateFailed(f"Could not download stolen vehicles list: {err}") from err

        vehicles, by_plate, newest = _parse_csv(text)
        if not vehicles:
            raise UpdateFailed("Police CSV was empty or could not be parsed")

        _LOGGER.debug(
            "Loaded %s stolen vehicles for %s",
            len(vehicles),
            district_label(district),
        )
        return StolenVehiclesData(
            vehicles=vehicles,
            by_plate=by_plate,
            newest_date=newest,
            district=district,
            source_url=url,
        )


def _parse_csv(text: str) -> tuple[list[dict[str, str]], dict[str, list[dict[str, str]]], str | None]:
    """Parse the headerless Police CSV into vehicle dicts."""
    vehicles: list[dict[str, str]] = []
    by_plate: dict[str, list[dict[str, str]]] = {}
    newest: str | None = None

    reader = csv.reader(io.StringIO(text))
    for row in reader:
        if len(row) < 8:
            continue
        plate = row[0].strip()
        key = normalize_plate(plate)
        if not key:
            continue
        vehicle = {
            _CSV_FIELDS[0]: plate,
            _CSV_FIELDS[1]: row[1].strip(),
            _CSV_FIELDS[2]: row[2].strip(),
            _CSV_FIELDS[3]: row[3].strip(),
            _CSV_FIELDS[4]: row[4].strip(),
            _CSV_FIELDS[5]: row[5].strip(),
            _CSV_FIELDS[6]: row[6].strip(),
            _CSV_FIELDS[7]: row[7].strip(),
        }
        vehicles.append(vehicle)
        by_plate.setdefault(key, []).append(vehicle)
        date_stolen = vehicle["date_stolen"]
        if date_stolen and (newest is None or date_stolen > newest):
            newest = date_stolen

    return vehicles, by_plate, newest
