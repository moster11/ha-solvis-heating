"""Fixtures for the Solvis Heating tests."""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path
from unittest.mock import AsyncMock, patch

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
from custom_components.solvis_heating.parser import SolvisData, parse_payload

FIXTURES = Path(__file__).parent / "fixtures"
HOST = "192.168.50.90"


def load_payload() -> str:
    """Return the recorded payload of a SolvisMax 6 (SC-2)."""
    return (FIXTURES / "sc2_payload.hex").read_text().strip()


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Enable loading of the custom integration."""


@pytest.fixture
def solvis_data() -> SolvisData:
    """Return decoded fixture data."""
    return parse_payload(load_payload())


@pytest.fixture
def mock_get_data(solvis_data: SolvisData) -> Generator[AsyncMock]:
    """Patch the client used by the integration and the config flow."""
    with patch(
        "custom_components.solvis_heating.api.SolvisRemoteClient.async_get_data",
        new=AsyncMock(return_value=solvis_data),
    ) as mock:
        yield mock


@pytest.fixture
def config_entry() -> MockConfigEntry:
    """Return a current (1.2) config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Solvis Remote",
        unique_id=HOST,
        version=1,
        minor_version=2,
        data={"host": HOST, "username": "solvis", "password": "secret"},
        options={
            CONF_WARMWATER_STATION: True,
            CONF_SOLAR: True,
            CONF_SOLAR_EAST_WEST: False,
            CONF_OVEN: False,
            CONF_UPDATE_INTERVAL: 30,
        },
    )
