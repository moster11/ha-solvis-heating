"""Constants for the Solvis Heating integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "solvis_heating"

DEFAULT_TITLE: Final = "Solvis Remote"
DEFAULT_USERNAME: Final = "solvis"
DEFAULT_PASSWORD: Final = "solvis"
MANUFACTURER: Final = "Solvis"

CONF_WARMWATER_STATION: Final = "warmwater_station"
CONF_SOLAR: Final = "solar"
CONF_SOLAR_EAST_WEST: Final = "east_west"
CONF_OVEN: Final = "oven"
CONF_UPDATE_INTERVAL: Final = "update_interval"

# Removed in 1.0.0, only read during migration.
CONF_LEGACY_BURNER_POWER: Final = "burner_power"

FEATURE_KEYS: Final = (
    CONF_WARMWATER_STATION,
    CONF_SOLAR,
    CONF_SOLAR_EAST_WEST,
    CONF_OVEN,
)
FEATURE_DEFAULTS: Final = {
    CONF_WARMWATER_STATION: True,
    CONF_SOLAR: True,
    CONF_SOLAR_EAST_WEST: False,
    CONF_OVEN: False,
}

DEFAULT_UPDATE_INTERVAL: Final = 30
LEGACY_DEFAULT_UPDATE_INTERVAL: Final = 10
MIN_UPDATE_INTERVAL: Final = 10
MAX_UPDATE_INTERVAL: Final = 300

# Polls in a row that may fail before entities become unavailable.
MAX_CONSECUTIVE_FAILURES: Final = 3

# Entities of 0.0.x that no longer exist (unique_id suffixes).
REMOVED_ENTITY_KEYS: Final = ("burner_capacity", "burner_consumption")

# The SC-2 reports a numeric system type; a SolvisMax 6 reports 8, so the
# old mapping (6 -> Max 6, 7 -> Max 7) was wrong. Only the raw id is shown.
DEVICE_MODEL: Final = "SolvisControl SC-2"
