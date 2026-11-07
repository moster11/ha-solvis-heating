"""Sensors of the Solvis Heating integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    EntityCategory,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfPressure,
    UnitOfTemperature,
    UnitOfTime,
    UnitOfVolumeFlowRate,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.util import dt as dt_util

from .coordinator import SolvisConfigEntry, SolvisCoordinator
from .entity import (
    SolvisEntity,
    SolvisEntityDescription,
    s16_unused,
    with_east_west,
    with_oven,
    with_solar,
    with_warmwater,
)

PARALLEL_UPDATES = 0

type ValueFn = Callable[[SolvisCoordinator], StateType | datetime]


def channel(name: str) -> ValueFn:
    """Return the decoded value of a channel."""
    return lambda coordinator: coordinator.data.get(name)


def _solar_delta(coordinator: SolvisCoordinator) -> float | None:
    flow = coordinator.data.get("S5")
    ret = coordinator.data.get("S6")
    if flow is None or ret is None:
        return None
    return round(flow - ret, 1)


def _controller_time(coordinator: SolvisCoordinator) -> datetime | None:
    value = coordinator.data.controller_datetime()
    if value is None:
        return None
    return value.replace(tzinfo=dt_util.get_default_time_zone())


@dataclass(frozen=True, kw_only=True)
class SolvisSensorEntityDescription(SolvisEntityDescription, SensorEntityDescription):
    """Describes a Solvis sensor."""

    value_fn: ValueFn


def _temperature(
    key: str, source: str, *, enabled: bool = True, exists_fn=None
) -> SolvisSensorEntityDescription:
    kwargs = {} if exists_fn is None else {"exists_fn": exists_fn}
    return SolvisSensorEntityDescription(
        key=key,
        translation_key=key,
        value_fn=channel(source),
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        entity_registry_enabled_default=enabled,
        **kwargs,
    )


SENSORS: tuple[SolvisSensorEntityDescription, ...] = (
    # Status
    SolvisSensorEntityDescription(
        key="last_update",
        translation_key="last_update",
        value_fn=lambda coordinator: coordinator.last_success,
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SolvisSensorEntityDescription(
        key="controller_time",
        translation_key="controller_time",
        value_fn=_controller_time,
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    # Buffer and heating
    _temperature("temperature_buffer_top", "S1"),
    _temperature("temperature_buffer_reference", "S3"),
    _temperature("temperature_buffer_heating_top", "S4"),
    _temperature("temperature_buffer_heating_bottom", "S9"),
    _temperature("temperature_outside", "S10"),
    _temperature("temperature_heating_circuit_1_flow", "S12"),
    _temperature("temperature_heating_circuit_2_flow", "S13"),
    _temperature("temperature_sensor_s14", "S14", enabled=False),
    _temperature("temperature_sensor_s15", "S15", enabled=False),
    _temperature("temperature_sensor_s16", "S16", enabled=False, exists_fn=s16_unused),
    _temperature("temperature_room_1", "RF1", enabled=False),
    _temperature("temperature_room_2", "RF2", enabled=False),
    _temperature("temperature_room_3", "RF3", enabled=False),
    # Burner
    SolvisSensorEntityDescription(
        key="runtime_burner",
        translation_key="runtime_burner",
        value_fn=channel("Z1"),
        native_unit_of_measurement=UnitOfTime.HOURS,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SolvisSensorEntityDescription(
        key="total_burner_start",
        translation_key="total_burner_start",
        value_fn=channel("Z2"),
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SolvisSensorEntityDescription(
        key="total_burner_2nd_start",
        translation_key="total_burner_2nd_start",
        value_fn=channel("Z3"),
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
    ),
    # Warm water
    _temperature("temperature_warm_water_station", "S2", exists_fn=with_warmwater),
    _temperature("temperature_circulation", "S11", exists_fn=with_warmwater),
    SolvisSensorEntityDescription(
        key="volume_stream_warm_water",
        translation_key="volume_stream_warm_water",
        value_fn=channel("S18"),
        native_unit_of_measurement=UnitOfVolumeFlowRate.LITERS_PER_MINUTE,
        device_class=SensorDeviceClass.VOLUME_FLOW_RATE,
        state_class=SensorStateClass.MEASUREMENT,
        exists_fn=with_warmwater,
    ),
    # Solar thermal
    _temperature("temperature_solar_flow", "S5", exists_fn=with_solar),
    _temperature("temperature_solar_return", "S6", exists_fn=with_solar),
    _temperature("temperature_solar_panel", "S8", exists_fn=with_solar),
    _temperature("temperature_solar_panel2", "S16", exists_fn=with_east_west),
    SolvisSensorEntityDescription(
        key="temperature_solar_diff_flow_return",
        translation_key="temperature_solar_diff_flow_return",
        value_fn=_solar_delta,
        native_unit_of_measurement=UnitOfTemperature.KELVIN,
        device_class=SensorDeviceClass.TEMPERATURE_DELTA,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        exists_fn=with_solar,
    ),
    SolvisSensorEntityDescription(
        key="solar_pressure",
        translation_key="solar_pressure",
        value_fn=channel("S7"),
        native_unit_of_measurement=UnitOfPressure.BAR,
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        exists_fn=with_solar,
    ),
    SolvisSensorEntityDescription(
        key="volume_stream_solar",
        translation_key="volume_stream_solar",
        value_fn=channel("S17"),
        native_unit_of_measurement=UnitOfVolumeFlowRate.LITERS_PER_HOUR,
        device_class=SensorDeviceClass.VOLUME_FLOW_RATE,
        state_class=SensorStateClass.MEASUREMENT,
        exists_fn=with_solar,
    ),
    SolvisSensorEntityDescription(
        key="solar_power",
        translation_key="solar_power",
        value_fn=channel("SL"),
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        exists_fn=with_solar,
    ),
    SolvisSensorEntityDescription(
        key="solar_yield",
        translation_key="solar_yield",
        value_fn=channel("SE"),
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        exists_fn=with_solar,
    ),
    SolvisSensorEntityDescription(
        key="runtime_solar_pump",
        translation_key="runtime_solar_pump",
        value_fn=channel("Z4"),
        native_unit_of_measurement=UnitOfTime.HOURS,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL_INCREASING,
        exists_fn=with_solar,
    ),
    # Oven
    _temperature("temperature_oven", "S16", exists_fn=with_oven),
    # Raw analog outputs (meaning depends on the system configuration)
    *(
        SolvisSensorEntityDescription(
            key=f"analog_output_{index}",
            translation_key="analog_output",
            translation_placeholders={"index": str(index)},
            value_fn=channel(f"AO{index}"),
            state_class=SensorStateClass.MEASUREMENT,
            entity_category=EntityCategory.DIAGNOSTIC,
            entity_registry_enabled_default=False,
        )
        for index in range(1, 5)
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SolvisConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensors."""
    coordinator = entry.runtime_data
    async_add_entities(
        SolvisSensor(coordinator, description)
        for description in SENSORS
        if description.exists_fn(entry.options)
    )


class SolvisSensor(SolvisEntity, SensorEntity):
    """A Solvis sensor."""

    entity_description: SolvisSensorEntityDescription

    @property
    def native_value(self) -> StateType | datetime:
        """Return the current value."""
        return self.entity_description.value_fn(self.coordinator)
