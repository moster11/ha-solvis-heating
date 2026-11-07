"""Exceptions for the Solvis Heating integration."""

from __future__ import annotations


class SolvisError(Exception):
    """Base error talking to the SolvisRemote."""


class SolvisConnectionError(SolvisError):
    """The SolvisRemote could not be reached or answered with an error."""


class SolvisAuthError(SolvisError):
    """The SolvisRemote rejected the credentials."""


class SolvisParseError(SolvisError):
    """The SolvisRemote answered with data that could not be decoded."""
