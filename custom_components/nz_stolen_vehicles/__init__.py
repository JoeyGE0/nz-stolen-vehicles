"""NZ Stolen Vehicles integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .blacklist import PlateBlacklist
from .const import DOMAIN
from .coordinator import StolenVehiclesCoordinator
from .services import async_setup_services, async_unload_services

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up NZ Stolen Vehicles from a config entry."""
    domain_data = hass.data.setdefault(DOMAIN, {})

    if "blacklist" not in domain_data:
        blacklist = PlateBlacklist(hass)
        await blacklist.async_load()
        domain_data["blacklist"] = blacklist

    coordinator = StolenVehiclesCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    domain_data[entry.entry_id] = coordinator
    await async_setup_services(hass)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        remaining = [
            key for key in hass.data[DOMAIN] if key != "blacklist"
        ]
        if not remaining:
            await async_unload_services(hass)
            hass.data.pop(DOMAIN, None)
    return unload_ok


async def _async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the config entry when options change."""
    await hass.config_entries.async_reload(entry.entry_id)
