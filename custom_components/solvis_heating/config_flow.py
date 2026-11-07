"""Config flow for the Solvis Heating integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from homeassistant.config_entries import (
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)
import voluptuous as vol

from .api import SolvisRemoteClient, normalize_host
from .const import (
    CONF_OVEN,
    CONF_REGISTRY_ID,
    CONF_SOLAR,
    CONF_SOLAR_EAST_WEST,
    CONF_UPDATE_INTERVAL,
    CONF_WARMWATER_STATION,
    DEFAULT_PASSWORD,
    DEFAULT_TITLE,
    DEFAULT_UPDATE_INTERVAL,
    DEFAULT_USERNAME,
    DOMAIN,
    FEATURE_DEFAULTS,
    MAX_UPDATE_INTERVAL,
    MIN_UPDATE_INTERVAL,
)
from .coordinator import SolvisConfigEntry
from .exceptions import SolvisAuthError, SolvisConnectionError, SolvisParseError

_LOGGER = logging.getLogger(__name__)

_PASSWORD_SELECTOR = TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))


def _connection_schema(defaults: Mapping[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_HOST, default=defaults.get(CONF_HOST, vol.UNDEFINED)): str,
            vol.Required(CONF_USERNAME, default=defaults.get(CONF_USERNAME, DEFAULT_USERNAME)): str,
            vol.Required(
                CONF_PASSWORD, default=defaults.get(CONF_PASSWORD, DEFAULT_PASSWORD)
            ): _PASSWORD_SELECTOR,
        }
    )


def _options_schema(defaults: Mapping[str, Any]) -> vol.Schema:
    def default(key: str) -> Any:
        return defaults.get(key, FEATURE_DEFAULTS.get(key, DEFAULT_UPDATE_INTERVAL))

    return vol.Schema(
        {
            vol.Required(CONF_WARMWATER_STATION, default=default(CONF_WARMWATER_STATION)): bool,
            vol.Required(CONF_SOLAR, default=default(CONF_SOLAR)): bool,
            vol.Required(CONF_SOLAR_EAST_WEST, default=default(CONF_SOLAR_EAST_WEST)): bool,
            vol.Required(CONF_OVEN, default=default(CONF_OVEN)): bool,
            vol.Required(
                CONF_UPDATE_INTERVAL, default=default(CONF_UPDATE_INTERVAL)
            ): NumberSelector(
                NumberSelectorConfig(
                    min=MIN_UPDATE_INTERVAL,
                    max=MAX_UPDATE_INTERVAL,
                    step=5,
                    mode=NumberSelectorMode.BOX,
                    unit_of_measurement="s",
                )
            ),
        }
    )


def _validate_options(user_input: dict[str, Any]) -> dict[str, str]:
    errors: dict[str, str] = {}
    if user_input[CONF_SOLAR_EAST_WEST] and not user_input[CONF_SOLAR]:
        errors[CONF_SOLAR_EAST_WEST] = "east_west_requires_solar"
    elif user_input[CONF_SOLAR_EAST_WEST] and user_input[CONF_OVEN]:
        # Both use sensor S16 on the SC-2.
        errors[CONF_OVEN] = "oven_conflicts_east_west"
    return errors


def _normalize_options(user_input: dict[str, Any]) -> dict[str, Any]:
    return {**user_input, CONF_UPDATE_INTERVAL: int(user_input[CONF_UPDATE_INTERVAL])}


def _orphaned_registry_id(hass: HomeAssistant) -> dict[str, str]:
    """Return the registry ID of a removed entry whose entities HA still keeps.

    When an entry is deleted, HA keeps the settings of its entities (entity ID,
    name, area, ...) for 30 days and restores them if an entity with the same
    unique_id appears again. A new entry adopts that prefix if it is unique.
    """
    in_use = {
        entry.data.get(CONF_REGISTRY_ID, entry.entry_id)
        for entry in hass.config_entries.async_entries(DOMAIN)
    }
    prefixes = {
        deleted.unique_id.split("_", 1)[0]
        for (_, platform, _), deleted in er.async_get(hass).deleted_entities.items()
        if platform == DOMAIN and deleted.config_entry_id is None and "_" in deleted.unique_id
    } - in_use
    if len(prefixes) == 1:
        prefix = prefixes.pop()
        _LOGGER.info("Adopting entities of removed entry %s", prefix)
        return {CONF_REGISTRY_ID: prefix}
    return {}


async def _async_validate_connection(
    hass: HomeAssistant, user_input: Mapping[str, Any]
) -> tuple[str, dict[str, str]]:
    """Try to read data; return the normalized host and errors."""
    host = normalize_host(user_input[CONF_HOST])
    client = SolvisRemoteClient(
        async_get_clientsession(hass),
        host,
        user_input[CONF_USERNAME],
        user_input[CONF_PASSWORD],
    )
    try:
        await client.async_get_data()
    except SolvisAuthError:
        return host, {"base": "invalid_auth"}
    except SolvisConnectionError:
        return host, {"base": "cannot_connect"}
    except SolvisParseError:
        return host, {"base": "invalid_data"}
    except Exception:
        _LOGGER.exception("Unexpected error validating the SolvisRemote")
        return host, {"base": "unknown"}
    return host, {}


class SolvisConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Solvis Heating."""

    VERSION = 1
    MINOR_VERSION = 2

    def __init__(self) -> None:
        """Initialize the flow."""
        self._connection: dict[str, Any] = {}

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Ask for the connection data of the SolvisRemote."""
        errors: dict[str, str] = {}
        if user_input is not None:
            host, errors = await _async_validate_connection(self.hass, user_input)
            if not errors:
                await self.async_set_unique_id(host)
                self._abort_if_unique_id_configured()
                self._connection = {**user_input, CONF_HOST: host}
                return await self.async_step_features()

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(_connection_schema({}), user_input),
            errors=errors,
        )

    async def async_step_features(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask which components are installed."""
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = _validate_options(user_input)
            if not errors:
                return self.async_create_entry(
                    title=DEFAULT_TITLE,
                    data={**self._connection, **_orphaned_registry_id(self.hass)},
                    options=_normalize_options(user_input),
                )

        return self.async_show_form(
            step_id="features",
            data_schema=_options_schema(user_input or {}),
            errors=errors,
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        """Handle rejected credentials."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for new credentials."""
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            data = {**entry.data, **user_input}
            _, errors = await _async_validate_connection(self.hass, data)
            if not errors:
                return self.async_update_reload_and_abort(entry, data_updates=user_input)

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME, default=entry.data[CONF_USERNAME]): str,
                    vol.Required(CONF_PASSWORD): _PASSWORD_SELECTOR,
                }
            ),
            description_placeholders={"host": entry.data[CONF_HOST]},
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Change host or credentials."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            host, errors = await _async_validate_connection(self.hass, user_input)
            if not errors:
                if host != entry.unique_id:
                    await self.async_set_unique_id(host)
                    self._abort_if_unique_id_configured()
                return self.async_update_reload_and_abort(
                    entry,
                    unique_id=host,
                    data_updates={**user_input, CONF_HOST: host},
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_connection_schema(user_input or entry.data),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: SolvisConfigEntry) -> SolvisOptionsFlow:
        """Create the options flow."""
        return SolvisOptionsFlow()


class SolvisOptionsFlow(OptionsFlowWithReload):
    """Change installed components and the polling interval."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Manage the options."""
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = _validate_options(user_input)
            if not errors:
                return self.async_create_entry(data=_normalize_options(user_input))

        return self.async_show_form(
            step_id="init",
            data_schema=_options_schema(user_input or self.config_entry.options),
            errors=errors,
        )
