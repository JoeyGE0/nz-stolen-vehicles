"""Sensor platform for NZ Stolen Vehicles."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTRIBUTION, DOMAIN, POLICE_PAGE_URL, district_label
from .coordinator import StolenVehiclesCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the stolen vehicles count sensor."""
    coordinator: StolenVehiclesCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([NZStolenVehiclesSensor(coordinator)])


class NZStolenVehiclesSensor(
    CoordinatorEntity[StolenVehiclesCoordinator], SensorEntity
):
    """Number of stolen vehicles in the configured Police list."""

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True
    _attr_icon = "mdi:car-emergency"
    _attr_name = None
    _attr_native_unit_of_measurement = "vehicles"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: StolenVehiclesCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_count"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.entry.entry_id)},
            name=f"NZ Stolen Vehicles ({district_label(coordinator.district)})",
            manufacturer="New Zealand Police",
            model="Stolen vehicles register",
            configuration_url=POLICE_PAGE_URL,
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def native_value(self) -> int | None:
        """Return the number of vehicles in the cached list."""
        if not self.coordinator.data:
            return None
        return len(self.coordinator.data.vehicles)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return metadata only — not the full plate list."""
        data = self.coordinator.data
        if not data:
            return {}
        return {
            "area": district_label(data.district),
            "district_id": data.district,
            "newest_date_stolen": data.newest_date,
            "last_refresh": (
                self.coordinator.last_update_success_time.isoformat()
                if self.coordinator.last_update_success_time
                else None
            ),
            "source": "https://www.police.govt.nz/can-you-help-us/stolen-vehicles",
        }
