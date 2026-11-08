"""Tests for setup, migration, entities and error handling."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed

from custom_components.solvis_heating.const import CONF_UPDATE_INTERVAL, DOMAIN
from custom_components.solvis_heating.diagnostics import async_get_config_entry_diagnostics
from custom_components.solvis_heating.exceptions import SolvisAuthError, SolvisConnectionError

from .conftest import HOST

LEGACY_ENTRY_ID = "a53a7b3c2ae952f60575af84bc0f2407"


async def _setup(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def test_setup_and_unload(
    hass: HomeAssistant, mock_get_data: AsyncMock, config_entry: MockConfigEntry
) -> None:
    """The entry loads, creates the device and unloads cleanly."""
    await _setup(hass, config_entry)
    assert config_entry.state is ConfigEntryState.LOADED

    device = dr.async_get(hass).async_get_device_by_identifier(
        (DOMAIN, config_entry.entry_id), config_entry.entry_id
    )
    assert device.manufacturer == "Solvis"
    assert device.model_id == "8"
    assert device.serial_number == "31"
    assert device.configuration_url == f"http://{HOST}"

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_not_ready(
    hass: HomeAssistant, mock_get_data: AsyncMock, config_entry: MockConfigEntry
) -> None:
    """An unreachable SolvisRemote retries setup later."""
    mock_get_data.side_effect = SolvisConnectionError("timeout")
    config_entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_entity_states(
    hass: HomeAssistant, mock_get_data: AsyncMock, config_entry: MockConfigEntry
) -> None:
    """Values, units and sentinels are mapped correctly."""
    await _setup(hass, config_entry)
    registry = er.async_get(hass)

    def entity_id(platform: str, key: str) -> str | None:
        return registry.async_get_entity_id(platform, DOMAIN, f"{config_entry.entry_id}_{key}")

    def state(platform: str, key: str):
        return hass.states.get(entity_id(platform, key))

    assert state("sensor", "temperature_buffer_top").state == "54.1"
    assert state("sensor", "temperature_buffer_top").attributes["unit_of_measurement"] == "°C"
    assert state("sensor", "temperature_heating_circuit_1_flow").state == "46.8"
    # Unconnected inputs report 250.0 °C and are now unknown.
    assert state("sensor", "solar_pressure").state == STATE_UNKNOWN
    assert state("sensor", "temperature_heating_circuit_2_flow").state == STATE_UNKNOWN

    delta = state("sensor", "temperature_solar_diff_flow_return")
    assert delta.state == "-0.5"
    assert delta.attributes["device_class"] == "temperature_delta"
    assert delta.attributes["unit_of_measurement"] == "K"

    flow = state("sensor", "volume_stream_solar")
    assert flow.attributes["unit_of_measurement"] == "L/h"
    assert flow.attributes["device_class"] == "volume_flow_rate"
    assert state("sensor", "volume_stream_warm_water").attributes["unit_of_measurement"] == "L/min"

    assert state("sensor", "runtime_burner").state == "17730"
    assert state("sensor", "runtime_burner").attributes["state_class"] == "total_increasing"
    assert state("sensor", "total_burner_start").state == "38536"
    assert state("sensor", "solar_yield").state == "21561"
    assert state("sensor", "last_update").state != STATE_UNKNOWN

    assert state("binary_sensor", "burner").state == "on"
    assert state("binary_sensor", "heating_circuit_1_pump").state == "on"
    assert state("binary_sensor", "solar_pump").state == "off"

    # German names come from the translations.
    assert state("binary_sensor", "burner").name == "Solvis Remote Burner"

    # Removed and disabled-by-default entities.
    assert entity_id("sensor", "burner_capacity") is None
    assert entity_id("sensor", "burner_consumption") is None
    for key in (
        "temperature_sensor_s14",
        "analog_output_1",
        "controller_time",
        "total_burner_2nd_start",
    ):
        entry = registry.async_get(entity_id("sensor", key))
        assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION, key
    # Option-dependent entities are not created.
    assert entity_id("sensor", "temperature_oven") is None
    assert entity_id("binary_sensor", "oven_pump") is None
    assert entity_id("binary_sensor", "solar_valve_1") is None
    assert entity_id("binary_sensor", "burner_s2") is not None


async def test_failure_tolerance(
    hass: HomeAssistant,
    mock_get_data: AsyncMock,
    config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Single failed polls keep the last values; repeated failures mark unavailable."""
    await _setup(hass, config_entry)
    entity_id = er.async_get(hass).async_get_entity_id(
        "binary_sensor", DOMAIN, f"{config_entry.entry_id}_burner"
    )
    mock_get_data.side_effect = SolvisConnectionError("timeout")

    for _ in range(2):
        freezer.tick(timedelta(seconds=30))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        assert hass.states.get(entity_id).state == "on"

    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE

    mock_get_data.side_effect = None
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == "on"


async def test_single_auth_failure_is_tolerated(
    hass: HomeAssistant,
    mock_get_data: AsyncMock,
    config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A sporadic 401 while running keeps the values and does not start reauth."""
    await _setup(hass, config_entry)
    entity_id = er.async_get(hass).async_get_entity_id(
        "binary_sensor", DOMAIN, f"{config_entry.entry_id}_burner"
    )
    mock_get_data.side_effect = [SolvisAuthError("401"), SolvisAuthError("401")]

    for _ in range(2):
        freezer.tick(timedelta(seconds=30))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        assert hass.states.get(entity_id).state == "on"

    mock_get_data.side_effect = None
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == "on"
    assert hass.config_entries.flow.async_progress_by_handler(DOMAIN) == []
    assert config_entry.state is ConfigEntryState.LOADED


async def test_repeated_auth_failure_starts_reauth(
    hass: HomeAssistant,
    mock_get_data: AsyncMock,
    config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Credentials rejected three times in a row start the reauth flow."""
    await _setup(hass, config_entry)
    mock_get_data.side_effect = SolvisAuthError("401")
    for _ in range(3):
        freezer.tick(timedelta(seconds=30))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert [flow["context"]["source"] for flow in flows] == ["reauth"]


async def test_mixed_failures_do_not_start_reauth(
    hass: HomeAssistant,
    mock_get_data: AsyncMock,
    config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Auth rejections only count when they happen in a row."""
    await _setup(hass, config_entry)
    mock_get_data.side_effect = [
        SolvisAuthError("401"),
        SolvisAuthError("401"),
        SolvisConnectionError("timeout"),
        SolvisAuthError("401"),
    ]
    for _ in range(4):
        freezer.tick(timedelta(seconds=30))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
    assert hass.config_entries.flow.async_progress_by_handler(DOMAIN) == []


async def test_auth_failure_on_setup_starts_reauth(
    hass: HomeAssistant, mock_get_data: AsyncMock, config_entry: MockConfigEntry
) -> None:
    """Rejected credentials during setup start reauth immediately."""
    mock_get_data.side_effect = SolvisAuthError("401")
    config_entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert [flow["context"]["source"] for flow in flows] == ["reauth"]


async def test_migration_from_0_0_x(hass: HomeAssistant, mock_get_data: AsyncMock) -> None:
    """Entries of 0.0.x keep their entities, lose the burner estimate and poll every 30 s."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        entry_id=LEGACY_ENTRY_ID,
        title="Solvis Remote",
        version=1,
        minor_version=1,
        unique_id=None,
        data={
            "host": f"{HOST}",
            "username": "solvis",
            "password": "secret",
            "warmwater_station": True,
            "solar": True,
            "east_west": False,
            "oven": False,
            "update_interval": 10,
        },
        # Written by the old (broken) options flow, never used.
        options={"east_west": True, "oven": True, "solar": False, "update_interval": 10},
    )
    entry.add_to_hass(hass)
    registry = er.async_get(hass)
    kept = registry.async_get_or_create(
        "sensor",
        DOMAIN,
        f"{LEGACY_ENTRY_ID}_temperature_buffer_heating_top",
        suggested_object_id="solvis_remote_temperature_h_buffer_top",
        config_entry=entry,
    )
    registry.async_update_entity(kept.entity_id, name="Heizungspuffer oben")
    removed = [
        registry.async_get_or_create(
            "sensor", DOMAIN, f"{LEGACY_ENTRY_ID}_{key}", config_entry=entry
        ).entity_id
        for key in ("burner_capacity", "burner_consumption")
    ]

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert entry.minor_version == 2
    assert entry.unique_id == HOST
    assert entry.data == {"host": HOST, "username": "solvis", "password": "secret"}
    assert entry.options == {
        "warmwater_station": True,
        "solar": True,
        "east_west": False,
        "oven": False,
        CONF_UPDATE_INTERVAL: 30,
    }
    assert entry.runtime_data.update_interval == timedelta(seconds=30)

    for entity_id in removed:
        assert registry.async_get(entity_id) is None
    state = hass.states.get("sensor.solvis_remote_temperature_h_buffer_top")
    assert state.state == "45.3"
    assert state.name == "Heizungspuffer oben"


async def test_diagnostics(
    hass: HomeAssistant, mock_get_data: AsyncMock, config_entry: MockConfigEntry
) -> None:
    """Credentials and host are redacted."""
    await _setup(hass, config_entry)
    result = await async_get_config_entry_diagnostics(hass, config_entry)
    assert result["entry"]["data"] == {
        "host": "**REDACTED**",
        "username": "**REDACTED**",
        "password": "**REDACTED**",
    }
    assert result["device_type"] == 8
    assert result["values"]["S1"] == 54.1
    assert result["raw_payload"].startswith("AA5555AA")
