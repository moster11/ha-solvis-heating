"""Base entity for the Solvis Heating integration."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_OVEN,
    CONF_SOLAR,
    CONF_SOLAR_EAST_WEST,
    CONF_WARMWATER_STATION,
    DEVICE_MODEL,
    DOMAIN,
    MANUFACTURER,
)
from .coordinator import SolvisCoordinator

type ExistsFn = Callable[[Mapping[str, Any]], bool]


def always(_: Mapping[str, Any]) -> bool:
    """Entity exists on every system."""
    return True


def with_warmwater(options: Mapping[str, Any]) -> bool:
    """Entity exists when a warm water station is installed."""
    return bool(options.get(CONF_WARMWATER_STATION))


def with_solar(options: Mapping[str, Any]) -> bool:
    """Entity exists when solar thermal is installed."""
    return bool(options.get(CONF_SOLAR))


def with_east_west(options: Mapping[str, Any]) -> bool:
    """Entity exists with an east/west solar field."""
    return bool(options.get(CONF_SOLAR)) and bool(options.get(CONF_SOLAR_EAST_WEST))


def without_east_west(options: Mapping[str, Any]) -> bool:
    """Entity exists unless A6/A7 drive the east/west solar valves."""
    return not with_east_west(options)


def with_oven(options: Mapping[str, Any]) -> bool:
    """Entity exists when a solid fuel oven is connected."""
    return bool(options.get(CONF_OVEN))


def without_oven(options: Mapping[str, Any]) -> bool:
    """Entity exists unless A13 drives the oven pump."""
    return not with_oven(options)


def s16_unused(options: Mapping[str, Any]) -> bool:
    """S16 is free when neither oven nor east/west solar use it."""
    return not with_oven(options) and not with_east_west(options)


@dataclass(frozen=True, kw_only=True)
class SolvisEntityDescription(EntityDescription):
    """Common fields of Solvis entity descriptions."""

    exists_fn: ExistsFn = always


class SolvisEntity(CoordinatorEntity[SolvisCoordinator]):
    """Base class for Solvis entities."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: SolvisCoordinator, description: EntityDescription) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.entity_description = description
        entry = coordinator.config_entry
        # unique_id format of 0.0.x is kept so entity IDs stay unchanged.
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        data = coordinator.data
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            manufacturer=MANUFACTURER,
            model=DEVICE_MODEL,
            model_id=str(data.device_type),
            serial_number=str(data.system_number),
            name=entry.title,
            configuration_url=coordinator.client.url,
        )
