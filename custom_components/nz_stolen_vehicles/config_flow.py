"""Config flow for NZ Stolen Vehicles."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import (
    CONF_DISTRICT,
    CONF_SCAN_INTERVAL,
    DEFAULT_DISTRICT,
    DEFAULT_SCAN_INTERVAL,
    DISTRICTS,
    DOMAIN,
    district_label,
)

DISTRICT_SELECTOR = SelectSelector(
    SelectSelectorConfig(
        options=[
            SelectOptionDict(value=value, label=label)
            for value, label in DISTRICTS.items()
        ],
        mode=SelectSelectorMode.DROPDOWN,
    )
)

INTERVAL_SELECTOR = NumberSelector(
    NumberSelectorConfig(min=1, max=24, step=1, mode=NumberSelectorMode.BOX, unit_of_measurement="hours")
)


def _schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    defaults = defaults or {}
    return vol.Schema(
        {
            vol.Required(
                CONF_DISTRICT,
                default=defaults.get(CONF_DISTRICT, DEFAULT_DISTRICT),
            ): DISTRICT_SELECTOR,
            vol.Required(
                CONF_SCAN_INTERVAL,
                default=defaults.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
            ): INTERVAL_SELECTOR,
        }
    )


class NZStolenVehiclesConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for NZ Stolen Vehicles."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial setup step."""
        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=_schema())

        district = str(user_input[CONF_DISTRICT])
        await self.async_set_unique_id(f"{DOMAIN}_{district}")
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=f"NZ Stolen Vehicles ({district_label(district)})",
            data={
                CONF_DISTRICT: district,
                CONF_SCAN_INTERVAL: int(user_input[CONF_SCAN_INTERVAL]),
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return the options flow."""
        return NZStolenVehiclesOptionsFlow()


class NZStolenVehiclesOptionsFlow(OptionsFlow):
    """Handle options for NZ Stolen Vehicles."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            district = str(user_input[CONF_DISTRICT])
            self.hass.config_entries.async_update_entry(
                self.config_entry,
                title=f"NZ Stolen Vehicles ({district_label(district)})",
                unique_id=f"{DOMAIN}_{district}",
            )
            return self.async_create_entry(
                title="",
                data={
                    CONF_DISTRICT: district,
                    CONF_SCAN_INTERVAL: int(user_input[CONF_SCAN_INTERVAL]),
                },
            )

        return self.async_show_form(
            step_id="init",
            data_schema=_schema(
                {
                    CONF_DISTRICT: self.config_entry.options.get(
                        CONF_DISTRICT,
                        self.config_entry.data.get(CONF_DISTRICT, DEFAULT_DISTRICT),
                    ),
                    CONF_SCAN_INTERVAL: self.config_entry.options.get(
                        CONF_SCAN_INTERVAL,
                        self.config_entry.data.get(
                            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                        ),
                    ),
                }
            ),
        )
