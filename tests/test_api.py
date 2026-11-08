"""Tests for the HTTP client, including digest authentication."""

from __future__ import annotations

import hashlib
import re

from aiohttp import ClientSession, web
from aiohttp.test_utils import TestServer
import pytest

from custom_components.solvis_heating.api import SolvisRemoteClient, normalize_host
from custom_components.solvis_heating.exceptions import (
    SolvisAuthError,
    SolvisConnectionError,
    SolvisParseError,
)

from .conftest import load_payload

pytestmark = pytest.mark.usefixtures("socket_enabled")

REALM = "SolvisRemote"
NONCE = "a1b2c3d4"


def _md5(value: str) -> str:
    return hashlib.md5(value.encode()).hexdigest()  # noqa: S324


def _digest_app(username: str, password: str, body: str, status: int = 200) -> web.Application:
    async def handler(request: web.Request) -> web.Response:
        header = request.headers.get("Authorization", "")
        if not header.startswith("Digest "):
            return web.Response(
                status=401,
                headers={
                    "WWW-Authenticate": (
                        f'Digest realm="{REALM}", nonce="{NONCE}", qop="auth", algorithm=MD5'
                    )
                },
            )
        fields = dict(re.findall(r'(\w+)="?([^",]+)"?', header[7:]))
        ha1 = _md5(f"{username}:{REALM}:{password}")
        ha2 = _md5(f"GET:{fields['uri']}")
        expected = _md5(
            f"{ha1}:{fields['nonce']}:{fields['nc']}:{fields['cnonce']}:{fields['qop']}:{ha2}"
        )
        if fields.get("username") != username or fields.get("response") != expected:
            return web.Response(
                status=401,
                headers={
                    "WWW-Authenticate": f'Digest realm="{REALM}", nonce="{NONCE}", qop="auth"'
                },
            )
        return web.Response(status=status, text=body, content_type="text/xml")

    app = web.Application()
    app.router.add_get("/sc2_val.xml", handler)
    return app


async def _client_for(app: web.Application, password: str = "solvis"):
    server = TestServer(app)
    await server.start_server()
    session = ClientSession()
    client = SolvisRemoteClient(session, f"http://{server.host}:{server.port}/", "solvis", password)
    return server, session, client


async def test_digest_auth_success() -> None:
    """Data is read with digest authentication."""
    app = _digest_app("solvis", "solvis", f"<xml><data>{load_payload()}</data></xml>")
    server, session, client = await _client_for(app)
    try:
        data = await client.async_get_data()
        # Second call reuses the digest challenge.
        data = await client.async_get_data()
    finally:
        await session.close()
        await server.close()
    assert data.get("S1") == 54.1


async def test_digest_auth_wrong_password() -> None:
    """Wrong credentials raise SolvisAuthError."""
    app = _digest_app("solvis", "solvis", "")
    server, session, client = await _client_for(app, password="wrong")
    try:
        with pytest.raises(SolvisAuthError):
            await client.async_get_data()
    finally:
        await session.close()
        await server.close()


async def test_server_error() -> None:
    """HTTP errors raise SolvisConnectionError."""
    app = _digest_app("solvis", "solvis", "error", status=500)
    server, session, client = await _client_for(app)
    try:
        with pytest.raises(SolvisConnectionError):
            await client.async_get_data()
    finally:
        await session.close()
        await server.close()


async def test_invalid_document() -> None:
    """A 200 response without payload raises SolvisParseError."""
    app = _digest_app("solvis", "solvis", "<html>busy</html>")
    server, session, client = await _client_for(app)
    try:
        with pytest.raises(SolvisParseError):
            await client.async_get_data()
    finally:
        await session.close()
        await server.close()


async def test_unreachable() -> None:
    """Connection failures raise SolvisConnectionError."""
    async with ClientSession() as session:
        client = SolvisRemoteClient(session, "127.0.0.1:9", "solvis", "solvis")
        with pytest.raises(SolvisConnectionError):
            await client.async_get_data()


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("192.168.50.90", "192.168.50.90"),
        (" http://192.168.50.90/ ", "192.168.50.90"),
        ("http://solvis.local:8080", "solvis.local:8080"),
        ("solvis.local/", "solvis.local"),
    ],
)
def test_normalize_host(value: str, expected: str) -> None:
    """User input is reduced to host[:port]."""
    assert normalize_host(value) == expected


async def test_sporadic_401_is_retried() -> None:
    """Valid credentials rejected twice (incl. the digest retry) are retried with a fresh state."""
    inner = _digest_app("solvis", "solvis", f"<xml><data>{load_payload()}</data></xml>")
    handler = inner.router.routes()._routes[0].handler
    calls = {"authorized": 0}

    async def flaky(request: web.Request) -> web.Response:
        if request.headers.get("Authorization", "").startswith("Digest "):
            calls["authorized"] += 1
            if calls["authorized"] in (2, 3):
                return web.Response(
                    status=401,
                    headers={
                        "WWW-Authenticate": f'Digest realm="{REALM}", nonce="other", qop="auth"'
                    },
                )
        return await handler(request)

    app = web.Application()
    app.router.add_get("/sc2_val.xml", flaky)
    server, session, client = await _client_for(app)
    try:
        await client.async_get_data()
        data = await client.async_get_data()
    finally:
        await session.close()
        await server.close()
    assert data.get("S1") == 54.1
