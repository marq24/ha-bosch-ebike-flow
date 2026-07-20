"""Diagnostics support for Bosch eBike."""
from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from . import KEY_COORDINATOR
from .const import CONF_BIKE_ID, CONF_BIKE_PASS, DOMAIN, OAUTH_TOKEN_KEY

# Keys that identify the bike/rider or grant API access - never include as-is in a
# diagnostics dump attached to a public bug report.
TO_REDACT = {
    OAUTH_TOKEN_KEY,
    CONF_BIKE_ID,
    CONF_BIKE_PASS,
    "latitude",
    "longitude",
    "frame",
    "frameNumber",
    "serialNumber",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id][KEY_COORDINATOR]

    return {
        "config_entry": {
            "data": async_redact_data(dict(config_entry.data), TO_REDACT),
            "options": dict(config_entry.options),
        },
        "coordinator": {
            "has_flow_subscription": coordinator.has_flow_subscription,
            "has_bcm": coordinator.has_bcm,
            "last_update_success": coordinator.last_update_success,
            "update_interval": str(coordinator.update_interval),
            "data": async_redact_data(coordinator.data, TO_REDACT) if coordinator.data else None,
        },
    }
