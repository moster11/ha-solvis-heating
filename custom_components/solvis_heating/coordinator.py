"""Data update coordinator for the Solvis Heating integration."""

from __future__ import annotations

from datetime import datetime, timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import SolvisRemoteClient
from .const import (
    CONF_UPDATE_INTERVAL,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    MAX_CONSECUTIVE_FAILURES,
)
from .exceptions import SolvisAuthError, SolvisError
from .parser import SolvisData

_LOGGER = logging.getLogger(__name__)

type SolvisConfigEntry = ConfigEntry[SolvisCoordinator]


class SolvisCoordinator(DataUpdateCoordinator[SolvisData]):
    """Poll the SolvisRemote."""

    config_entry: SolvisConfigEntry

    def __init__(
        self, hass: HomeAssistant, entry: SolvisConfigEntry, client: SolvisRemoteClient
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(
                seconds=entry.options.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)
            ),
        )
        self.client = client
        self.last_success: datetime | None = None
        self._failures = 0

    async def _async_update_data(self) -> SolvisData:
        """Fetch new data; tolerate a few failed polls in a row."""
        try:
            data = await self.client.async_get_data()
        except SolvisAuthError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN, translation_key="auth_failed"
            ) from err
        except SolvisError as err:
            self._failures += 1
            if self.data is not None and self._failures < MAX_CONSECUTIVE_FAILURES:
                _LOGGER.debug(
                    "Poll %s/%s failed, keeping last values: %s",
                    self._failures,
                    MAX_CONSECUTIVE_FAILURES,
                    err,
                )
                return self.data
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
                translation_placeholders={"error": str(err)},
            ) from err

        if self._failures:
            _LOGGER.debug("Poll succeeded again after %s failure(s)", self._failures)
        self._failures = 0
        self.last_success = dt_util.utcnow()
        return data
