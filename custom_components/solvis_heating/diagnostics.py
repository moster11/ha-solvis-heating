"""Diagnostics support for the Solvis Heating integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .coordinator import SolvisConfigEntry

TO_REDACT = {CONF_HOST, CONF_PASSWORD, CONF_USERNAME}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: SolvisConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data
    data = coordinator.data
    controller_time = data.controller_datetime()
    return {
        "entry": {
            "data": async_redact_data(dict(entry.data), TO_REDACT),
            "options": dict(entry.options),
        },
        "last_success": coordinator.last_success,
        "last_update_success": coordinator.last_update_success,
        "device_type": data.device_type,
        "system_number": data.system_number,
        "controller_time": controller_time.isoformat() if controller_time else None,
        "values": data.values,
        "raw_payload": data.raw,
    }
