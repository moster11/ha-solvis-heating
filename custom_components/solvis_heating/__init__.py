"""The Solvis Heating integration."""

from __future__ import annotations

import logging

from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import SolvisRemoteClient, normalize_host
from .const import (
    CONF_UPDATE_INTERVAL,
    DEFAULT_UPDATE_INTERVAL,
    FEATURE_DEFAULTS,
    FEATURE_KEYS,
    LEGACY_DEFAULT_UPDATE_INTERVAL,
    MAX_UPDATE_INTERVAL,
    MIN_UPDATE_INTERVAL,
    REMOVED_ENTITY_KEYS,
)
from .coordinator import SolvisConfigEntry, SolvisCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: SolvisConfigEntry) -> bool:
    """Set up Solvis Heating from a config entry."""
    client = SolvisRemoteClient(
        async_get_clientsession(hass),
        entry.data[CONF_HOST],
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
    )
    coordinator = SolvisCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    # The options flow (OptionsFlowWithReload) reloads the entry on change.
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: SolvisConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_entry(hass: HomeAssistant, entry: SolvisConfigEntry) -> bool:
    """Migrate entries created by 0.0.x."""
    if entry.version > 1:
        return False

    if entry.minor_version < 2:
        # 0.0.x kept the feature flags in data and ignored options entirely.
        options = {key: entry.data.get(key, FEATURE_DEFAULTS[key]) for key in FEATURE_KEYS}
        interval = entry.data.get(CONF_UPDATE_INTERVAL, LEGACY_DEFAULT_UPDATE_INTERVAL)
        if interval == LEGACY_DEFAULT_UPDATE_INTERVAL:
            interval = DEFAULT_UPDATE_INTERVAL
        options[CONF_UPDATE_INTERVAL] = max(
            MIN_UPDATE_INTERVAL, min(MAX_UPDATE_INTERVAL, int(interval))
        )
        host = normalize_host(entry.data[CONF_HOST])
        data = {
            CONF_HOST: host,
            CONF_USERNAME: entry.data[CONF_USERNAME],
            CONF_PASSWORD: entry.data[CONF_PASSWORD],
        }

        registry = er.async_get(hass)
        for key in REMOVED_ENTITY_KEYS:
            if entity_id := registry.async_get_entity_id(
                Platform.SENSOR, entry.domain, f"{entry.entry_id}_{key}"
            ):
                _LOGGER.info("Removing obsolete entity %s", entity_id)
                registry.async_remove(entity_id)

        unique_id = entry.unique_id
        if unique_id is None and not any(
            other.unique_id == host
            for other in hass.config_entries.async_entries(entry.domain)
            if other.entry_id != entry.entry_id
        ):
            unique_id = host

        hass.config_entries.async_update_entry(
            entry,
            data=data,
            options=options,
            unique_id=unique_id,
            minor_version=2,
        )
        _LOGGER.info("Migrated Solvis Heating entry to version 1.2")

    return True
