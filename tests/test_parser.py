"""Tests for the payload parser."""

from __future__ import annotations

from datetime import datetime, time

import pytest

from custom_components.solvis_heating.exceptions import SolvisParseError
from custom_components.solvis_heating.parser import extract_payload, parse_payload

from .conftest import load_payload


def test_parse_recorded_payload() -> None:
    """Decode a real SolvisMax 6 payload."""
    data = parse_payload(load_payload())

    assert data.device_type == 8
    assert data.system_number == 31
    assert data.controller_time == time(17, 11, 25)
    assert data.controller_datetime() == datetime(2026, 11, 7, 17, 11, 25)

    expected = {
        "S1": 54.1,
        "S2": 45.0,
        "S3": 35.0,
        "S4": 45.3,
        "S5": 20.4,
        "S6": 20.9,
        "S8": 2.2,
        "S9": 39.4,
        "S10": 5.2,
        "S11": 35.0,
        "S12": 46.8,
        "S14": 40.0,
        "S15": 20.2,
        "S17": 0,
        "S18": 0.0,
        "Z1": 17730,
        "Z2": 38536,
        "Z4": 9201,
        "SE": 21561,
        "SL": 0.0,
        "AO1": 61,
        "AO2": 76,
        "AO3": 76,
        "AO4": 13,
        "A3": 100,
        "A12": 100,
        "A14": 100,
        "A1": 0,
    }
    for channel, value in expected.items():
        assert data.get(channel) == value, channel


@pytest.mark.parametrize("channel", ["S7", "S13", "S16"])
def test_unconnected_temperature_is_none(channel: str) -> None:
    """250.0 °C marks an input without sensor."""
    assert parse_payload(load_payload()).get(channel) is None


def test_unavailable_counter_is_none() -> None:
    """0xFFFF marks a counter that does not exist."""
    assert parse_payload(load_payload()).get("Z3") is None


def test_negative_temperature() -> None:
    """Temperatures are signed."""
    payload = load_payload()
    # S10 (outside) starts at offset 26 + 9 * 4 = 62; -5.5 °C = 0xFFC9.
    payload = payload[:62] + "C9FF" + payload[66:]
    assert parse_payload(payload).get("S10") == -5.5


def test_extract_payload() -> None:
    """The hex string is read from the <data> element."""
    document = f"<xml>\n<data>{load_payload().lower()}</data>\n</xml>"
    assert extract_payload(document) == load_payload()


@pytest.mark.parametrize("document", ["<xml></xml>", "<html>Login</html>", "", "<data>xyz</data>"])
def test_extract_payload_invalid(document: str) -> None:
    """Responses without hex data are rejected."""
    with pytest.raises(SolvisParseError):
        extract_payload(document)


def test_short_payload() -> None:
    """A truncated payload is rejected instead of yielding empty data."""
    with pytest.raises(SolvisParseError):
        parse_payload(load_payload()[:100])


def test_payload_without_date() -> None:
    """The date block is optional."""
    data = parse_payload(load_payload()[:212])
    assert data.controller_date is None
    assert data.controller_datetime() is None
    assert data.get("SL") == 0.0
