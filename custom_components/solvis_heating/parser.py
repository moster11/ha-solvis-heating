"""Decoder for the SolvisRemote ``sc2_val.xml`` payload.

The byte layout is based on the ``sc2xmlreader`` package by Lurchi70
(MIT License, Copyright (c) 2023 Lurchi70) and was extended and verified
against a live SolvisMax 6 / SC-2 payload.

All multi-byte values are little-endian. Offsets below are in hex characters.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, time
import re

from .exceptions import SolvisParseError

_DATA_RE = re.compile(r"<data>\s*([0-9A-Fa-f]+)\s*</data>", re.DOTALL)

# Raw value the SC-2 reports for a temperature input without a sensor
# (250.0 °C). Seen on S7, S13 and S16 of a system without those sensors.
TEMPERATURE_NOT_CONNECTED = 2500
# Counters report 0xFFFF when the function does not exist (e.g. no 2nd stage).
COUNTER_NOT_AVAILABLE = 0xFFFF

TEMPERATURE_CHANNELS = tuple(f"S{i}" for i in range(1, 17))
ROOM_CHANNELS = ("RF1", "RF2", "RF3")
ANALOG_IN_CHANNELS = ("AI1", "AI2", "AI3")
ANALOG_OUT_CHANNELS = ("AO1", "AO2", "AO3", "AO4")
OUTPUT_CHANNELS = tuple(f"A{i}" for i in range(1, 15))
COUNTER_CHANNELS = ("Z1", "Z2", "Z3", "Z4", "SE")

# Last field that must be present (solar power, ends at offset 212).
_MIN_LENGTH = 212


@dataclass(frozen=True, slots=True)
class SolvisData:
    """Decoded values of one SolvisRemote poll."""

    device_type: int
    system_number: int
    controller_time: time | None
    controller_date: tuple[int, int, int] | None
    values: dict[str, float | int | None] = field(default_factory=dict)
    raw: str = ""

    def get(self, channel: str) -> float | int | None:
        """Return the decoded value of a channel (None if not available)."""
        return self.values.get(channel)

    def controller_datetime(self) -> datetime | None:
        """Return the controller clock as naive local datetime, if complete."""
        if self.controller_time is None or self.controller_date is None:
            return None
        year, month, day = self.controller_date
        try:
            return datetime.combine(datetime(2000 + year, month, day).date(), self.controller_time)
        except ValueError:
            return None


class _Reader:
    """Sequential reader over the hex payload."""

    def __init__(self, payload: str) -> None:
        self._payload = payload
        self.pos = 0

    def raw(self, chars: int) -> str:
        chunk = self._payload[self.pos : self.pos + chars]
        if len(chunk) != chars:
            raise SolvisParseError(f"payload truncated at offset {self.pos}")
        self.pos += chars
        return chunk

    def uint(self, size_bytes: int) -> int:
        chunk = self.raw(size_bytes * 2)
        return int.from_bytes(bytes.fromhex(chunk), "little")

    def int16(self) -> int:
        value = self.uint(2)
        return value - 0x10000 if value > 0x7FFF else value


def extract_payload(document: str) -> str:
    """Extract the hex payload from the XML document."""
    match = _DATA_RE.search(document)
    if match is None:
        raise SolvisParseError("no <data> element in response")
    return match.group(1).upper()


def _temperature(raw: int) -> float | None:
    if raw == TEMPERATURE_NOT_CONNECTED:
        return None
    return raw / 10


def _counter(raw: int) -> int | None:
    return None if raw == COUNTER_NOT_AVAILABLE else raw


def _parse_time(chunk: str) -> time | None:
    hour, minute, second = bytes.fromhex(chunk)
    try:
        return time(hour, minute, second)
    except ValueError:
        return None


def parse_payload(payload: str) -> SolvisData:
    """Decode a hex payload into SolvisData."""
    payload = payload.strip().upper()
    if len(payload) < _MIN_LENGTH:
        raise SolvisParseError(f"payload too short ({len(payload)} < {_MIN_LENGTH} characters)")
    try:
        bytes.fromhex(payload[:_MIN_LENGTH])
    except ValueError as err:
        raise SolvisParseError("payload is not hex encoded") from err

    reader = _Reader(payload)
    values: dict[str, float | int | None] = {}

    reader.raw(12)  # header
    controller_time = _parse_time(reader.raw(6))
    device_type = reader.uint(2)
    system_number = reader.uint(2)

    for channel in TEMPERATURE_CHANNELS:
        values[channel] = _temperature(reader.int16())

    # Flow rates: S18 warm water (l/min, 1 decimal), S17 solar (l/h).
    values["S18"] = reader.uint(2) / 10
    values["S17"] = reader.uint(2)

    for channel in ANALOG_IN_CHANNELS:
        values[channel] = reader.uint(2)
    for channel in ANALOG_OUT_CHANNELS:
        values[channel] = reader.uint(1)
    for channel in ROOM_CHANNELS:
        values[channel] = _temperature(reader.int16())
    for channel in OUTPUT_CHANNELS:
        values[channel] = reader.uint(1)
    for channel in COUNTER_CHANNELS:
        values[channel] = _counter(reader.uint(2))

    reader.raw(30)  # status bytes, meaning unknown
    values["SL"] = reader.uint(2) / 10  # solar power, kW

    controller_date: tuple[int, int, int] | None = None
    if len(payload) >= reader.pos + 8:
        reader.raw(2)
        year, month, day = bytes.fromhex(reader.raw(6))
        if 1 <= month <= 12 and 1 <= day <= 31:
            controller_date = (year, month, day)

    return SolvisData(
        device_type=device_type,
        system_number=system_number,
        controller_time=controller_time,
        controller_date=controller_date,
        values=values,
        raw=payload,
    )
