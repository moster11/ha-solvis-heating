"""Tests for the config, options, reauth and reconfigure flows."""

from __future__ import annotations

from unittest.mock import AsyncMock

from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.solvis_heating.const import (
    CONF_OVEN,
    CONF_SOLAR,
    CONF_SOLAR_EAST_WEST,
    CONF_UPDATE_INTERVAL,
    CONF_WARMWATER_STATION,
    DOMAIN,
)
from custom_components.solvis_heating.exceptions import (
    SolvisAuthError,
    SolvisConnectionError,
    SolvisParseError,
)

from .conftest import HOST

FEATURES = {
    CONF_WARMWATER_STATION: True,
    CONF_SOLAR: True,
    CONF_SOLAR_EAST_WEST: False,
    CONF_OVEN: False,
    CONF_UPDATE_INTERVAL: 30.0,
}


async def test_user_flow(hass: HomeAssistant, mock_get_data: AsyncMock) -> None:
    """A complete setup creates an entry with data and options."""
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"host": f"http://{HOST}/", "username": "solvis", "password": "secret"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "features"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], FEATURES)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Solvis Remote"
    assert result["data"] == {"host": HOST, "username": "solvis", "password": "secret"}
    assert result["options"][CONF_UPDATE_INTERVAL] == 30
    assert result["result"].unique_id == HOST


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (SolvisAuthError, "invalid_auth"),
        (SolvisConnectionError, "cannot_connect"),
        (SolvisParseError, "invalid_data"),
        (RuntimeError, "unknown"),
    ],
)
async def test_user_flow_errors(
    hass: HomeAssistant, mock_get_data: AsyncMock, error: type[Exception], expected: str
) -> None:
    """Connection problems are shown and the flow can recover."""
    mock_get_data.side_effect = error
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    user_input = {"host": HOST, "username": "solvis", "password": "secret"}
    result = await hass.config_entries.flow.async_configure(result["flow_id"], user_input)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected}

    mock_get_data.side_effect = None
    result = await hass.config_entries.flow.async_configure(result["flow_id"], user_input)
    assert result["step_id"] == "features"


async def test_feature_validation(hass: HomeAssistant, mock_get_data: AsyncMock) -> None:
    """Invalid feature combinations are rejected."""
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"host": HOST, "username": "solvis", "password": "secret"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**FEATURES, CONF_SOLAR: False, CONF_SOLAR_EAST_WEST: True}
    )
    assert result["errors"] == {CONF_SOLAR_EAST_WEST: "east_west_requires_solar"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**FEATURES, CONF_SOLAR_EAST_WEST: True, CONF_OVEN: True}
    )
    assert result["errors"] == {CONF_OVEN: "oven_conflicts_east_west"}


async def test_already_configured(
    hass: HomeAssistant, mock_get_data: AsyncMock, config_entry: MockConfigEntry
) -> None:
    """The same SolvisRemote cannot be added twice."""
    config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"host": HOST, "username": "solvis", "password": "secret"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_options_flow(
    hass: HomeAssistant, mock_get_data: AsyncMock, config_entry: MockConfigEntry
) -> None:
    """Options are prefilled, validated, stored and trigger a reload."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    schema = result["data_schema"].schema
    defaults = {str(key): key.default() for key in schema}
    assert defaults[CONF_UPDATE_INTERVAL] == 30

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {**FEATURES, CONF_SOLAR: False, CONF_SOLAR_EAST_WEST: True}
    )
    assert result["errors"] == {CONF_SOLAR_EAST_WEST: "east_west_requires_solar"}

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {**FEATURES, CONF_UPDATE_INTERVAL: 60.0}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert config_entry.options[CONF_UPDATE_INTERVAL] == 60
    assert config_entry.runtime_data.update_interval.total_seconds() == 60


async def test_reauth_flow(
    hass: HomeAssistant, mock_get_data: AsyncMock, config_entry: MockConfigEntry
) -> None:
    """New credentials are validated and stored."""
    config_entry.add_to_hass(hass)
    result = await config_entry.start_reauth_flow(hass)
    assert result["step_id"] == "reauth_confirm"

    mock_get_data.side_effect = SolvisAuthError
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"username": "solvis", "password": "wrong"}
    )
    assert result["errors"] == {"base": "invalid_auth"}

    mock_get_data.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"username": "solvis", "password": "new"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert config_entry.data["password"] == "new"


async def test_reconfigure_flow(
    hass: HomeAssistant, mock_get_data: AsyncMock, config_entry: MockConfigEntry
) -> None:
    """Host changes update data and unique_id."""
    config_entry.add_to_hass(hass)
    result = await config_entry.start_reconfigure_flow(hass)
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"host": "192.168.50.91", "username": "solvis", "password": "secret"},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert config_entry.data["host"] == "192.168.50.91"
    assert config_entry.unique_id == "192.168.50.91"
