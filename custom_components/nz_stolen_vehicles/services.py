"""Services for NZ Stolen Vehicles."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv

from .blacklist import PlateBlacklist
from .const import (
    DOMAIN,
    EVENT_MATCH,
    SERVICE_ADD_BLACKLIST,
    SERVICE_CHECK_PLATE,
    SERVICE_REMOVE_BLACKLIST,
    SOURCE_BLACKLIST,
    SOURCE_POLICE,
    normalize_plate,
)
from .coordinator import StolenVehiclesCoordinator

_LOGGER = logging.getLogger(__name__)

CHECK_SCHEMA = vol.Schema(
    {
        vol.Required("plate"): cv.string,
    }
)

ADD_BLACKLIST_SCHEMA = vol.Schema(
    {
        vol.Required("plate"): cv.string,
        vol.Optional("reason", default=""): cv.string,
    }
)

REMOVE_BLACKLIST_SCHEMA = vol.Schema(
    {
        vol.Required("plate"): cv.string,
    }
)

_SERVICES = (
    SERVICE_CHECK_PLATE,
    SERVICE_ADD_BLACKLIST,
    SERVICE_REMOVE_BLACKLIST,
)


def _blacklist(hass: HomeAssistant) -> PlateBlacklist:
    return hass.data[DOMAIN]["blacklist"]


def _coordinators(hass: HomeAssistant) -> list[StolenVehiclesCoordinator]:
    return [
        value
        for key, value in hass.data.get(DOMAIN, {}).items()
        if key != "blacklist" and isinstance(value, StolenVehiclesCoordinator)
    ]


def _tag_police(matches: list[dict[str, Any]]) -> list[dict[str, Any]]:
    tagged: list[dict[str, Any]] = []
    for item in matches:
        row = dict(item)
        row.setdefault("source", SOURCE_POLICE)
        row.setdefault("reason", "")
        tagged.append(row)
    return tagged


async def async_setup_services(hass: HomeAssistant) -> None:
    """Register integration services once."""
    if hass.services.has_service(DOMAIN, SERVICE_CHECK_PLATE):
        return

    async def handle_check_plate(call: ServiceCall) -> ServiceResponse:
        raw_plate = call.data["plate"]
        plate = normalize_plate(raw_plate)
        police_matches: list[dict[str, Any]] = []

        for coordinator in _coordinators(hass):
            police_matches.extend(_tag_police(coordinator.lookup(plate)))

        blacklist = _blacklist(hass)
        await blacklist.async_load()
        blacklist_matches = blacklist.lookup(plate)
        matches = police_matches + blacklist_matches

        result: ServiceResponse = {
            "stolen": bool(police_matches),
            "blacklisted": bool(blacklist_matches),
            "plate": raw_plate,
            "normalized_plate": plate,
            "match_count": len(matches),
            "matches": matches,
        }

        if matches:
            hass.bus.async_fire(EVENT_MATCH, result)
            sources = ", ".join(
                sorted({str(item.get("source", "")) for item in matches})
            )
            _LOGGER.info(
                "Vehicle match for %s (%s): %s",
                raw_plate,
                sources,
                ", ".join(
                    (
                        f"{item.get('colour', '')} {item.get('make', '')} "
                        f"{item.get('model', '')}".strip()
                        or item.get("reason")
                        or item.get("source", "match")
                    )
                    for item in matches
                ),
            )

        return result

    async def handle_add_blacklist(call: ServiceCall) -> ServiceResponse:
        try:
            return await _blacklist(hass).async_add(
                call.data["plate"],
                call.data.get("reason", ""),
            )
        except ValueError as err:
            raise HomeAssistantError(str(err)) from err

    async def handle_remove_blacklist(call: ServiceCall) -> ServiceResponse:
        return await _blacklist(hass).async_remove(call.data["plate"])

    hass.services.async_register(
        DOMAIN,
        SERVICE_CHECK_PLATE,
        handle_check_plate,
        schema=CHECK_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_ADD_BLACKLIST,
        handle_add_blacklist,
        schema=ADD_BLACKLIST_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_REMOVE_BLACKLIST,
        handle_remove_blacklist,
        schema=REMOVE_BLACKLIST_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )


async def async_unload_services(hass: HomeAssistant) -> None:
    """Remove services when the last config entry unloads."""
    for service in _SERVICES:
        if hass.services.has_service(DOMAIN, service):
            hass.services.async_remove(DOMAIN, service)
