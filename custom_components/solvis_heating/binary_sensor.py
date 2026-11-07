"""Binary sensors (switching outputs) of the Solvis Heating integration."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import SolvisConfigEntry
from .entity import (
    SolvisEntity,
    SolvisEntityDescription,
    with_east_west,
    with_oven,
    with_solar,
    with_warmwater,
    without_east_west,
    without_oven,
)

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class SolvisBinarySensorEntityDescription(SolvisEntityDescription, BinarySensorEntityDescription):
    """Describes a Solvis switching output."""

    channel: str
    device_class: BinarySensorDeviceClass | None = BinarySensorDeviceClass.RUNNING


BINARY_SENSORS: tuple[SolvisBinarySensorEntityDescription, ...] = (
    SolvisBinarySensorEntityDescription(
        key="solar_pump", translation_key="solar_pump", channel="A1", exists_fn=with_solar
    ),
    SolvisBinarySensorEntityDescription(
        key="warm_water_station_pump",
        translation_key="warm_water_station_pump",
        channel="A2",
        exists_fn=with_warmwater,
    ),
    SolvisBinarySensorEntityDescription(
        key="heating_circuit_1_pump", translation_key="heating_circuit_1_pump", channel="A3"
    ),
    SolvisBinarySensorEntityDescription(
        key="heating_circuit_2_pump", translation_key="heating_circuit_2_pump", channel="A4"
    ),
    SolvisBinarySensorEntityDescription(
        key="circulation_pump",
        translation_key="circulation_pump",
        channel="A5",
        exists_fn=with_warmwater,
    ),
    SolvisBinarySensorEntityDescription(
        key="heating_circuit_3_pump",
        translation_key="heating_circuit_3_pump",
        channel="A6",
        exists_fn=without_east_west,
    ),
    SolvisBinarySensorEntityDescription(
        key="solar_valve_1",
        translation_key="solar_valve_1",
        channel="A6",
        exists_fn=with_east_west,
    ),
    SolvisBinarySensorEntityDescription(
        key="solar_valve_2",
        translation_key="solar_valve_2",
        channel="A7",
        exists_fn=with_east_west,
    ),
    SolvisBinarySensorEntityDescription(
        key="heating_circuit_1_mixer_open",
        translation_key="heating_circuit_1_mixer_open",
        channel="A8",
    ),
    SolvisBinarySensorEntityDescription(
        key="heating_circuit_1_mixer_close",
        translation_key="heating_circuit_1_mixer_close",
        channel="A9",
    ),
    SolvisBinarySensorEntityDescription(
        key="heating_circuit_2_mixer_open",
        translation_key="heating_circuit_2_mixer_open",
        channel="A10",
    ),
    SolvisBinarySensorEntityDescription(
        key="heating_circuit_2_mixer_close",
        translation_key="heating_circuit_2_mixer_close",
        channel="A11",
    ),
    SolvisBinarySensorEntityDescription(key="burner", translation_key="burner", channel="A12"),
    SolvisBinarySensorEntityDescription(
        key="burner_s2", translation_key="burner_s2", channel="A13", exists_fn=without_oven
    ),
    SolvisBinarySensorEntityDescription(
        key="oven_pump", translation_key="oven_pump", channel="A13", exists_fn=with_oven
    ),
    SolvisBinarySensorEntityDescription(key="recovery", translation_key="recovery", channel="A14"),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SolvisConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the binary sensors."""
    coordinator = entry.runtime_data
    async_add_entities(
        SolvisBinarySensor(coordinator, description)
        for description in BINARY_SENSORS
        if description.exists_fn(entry.options)
    )


class SolvisBinarySensor(SolvisEntity, BinarySensorEntity):
    """A switching output of the SC-2 (0 = off, >0 = on)."""

    entity_description: SolvisBinarySensorEntityDescription

    @property
    def is_on(self) -> bool | None:
        """Return true if the output is active."""
        value = self.coordinator.data.get(self.entity_description.channel)
        return None if value is None else value > 0
