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
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN, EVENT_MATCH, SERVICE_CHECK_PLATE, normalize_plate
from .coordinator import StolenVehiclesCoordinator

_LOGGER = logging.getLogger(__name__)

SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required("plate"): cv.string,
    }
)


async def async_setup_services(hass: HomeAssistant) -> None:
    """Register integration services once."""
    if hass.services.has_service(DOMAIN, SERVICE_CHECK_PLATE):
        return

    async def handle_check_plate(call: ServiceCall) -> ServiceResponse:
        raw_plate = call.data["plate"]
        plate = normalize_plate(raw_plate)
        matches: list[dict[str, Any]] = []

        coordinators: list[StolenVehiclesCoordinator] = list(
            hass.data.get(DOMAIN, {}).values()
        )
        for coordinator in coordinators:
            matches.extend(coordinator.lookup(plate))

        result: ServiceResponse = {
            "stolen": bool(matches),
            "plate": raw_plate,
            "normalized_plate": plate,
            "match_count": len(matches),
            "matches": matches,
        }

        if matches:
            hass.bus.async_fire(EVENT_MATCH, result)
            _LOGGER.info(
                "Stolen vehicle match for %s (%s)",
                raw_plate,
                ", ".join(
                    f"{item.get('colour', '')} {item.get('make', '')} {item.get('model', '')}".strip()
                    for item in matches
                ),
            )

        return result

    hass.services.async_register(
        DOMAIN,
        SERVICE_CHECK_PLATE,
        handle_check_plate,
        schema=SERVICE_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
