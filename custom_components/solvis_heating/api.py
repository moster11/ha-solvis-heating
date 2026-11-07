"""Async client for the SolvisRemote XML interface."""

from __future__ import annotations

from urllib.parse import urlsplit

from aiohttp import ClientError, ClientSession, ClientTimeout, DigestAuthMiddleware

from .exceptions import SolvisAuthError, SolvisConnectionError
from .parser import SolvisData, extract_payload, parse_payload

_TIMEOUT = ClientTimeout(total=10)
_PATH = "/sc2_val.xml"


def normalize_host(host: str) -> str:
    """Return host[:port] from user input such as 'http://1.2.3.4/'."""
    host = host.strip()
    parts = urlsplit(host if "//" in host else f"//{host}")
    return (parts.netloc or parts.path).rstrip("/")


class SolvisRemoteClient:
    """Read the current values from a SolvisRemote."""

    def __init__(self, session: ClientSession, host: str, username: str, password: str) -> None:
        """Initialize the client."""
        self._session = session
        self.host = normalize_host(host)
        self._auth = DigestAuthMiddleware(username, password)

    @property
    def url(self) -> str:
        """Base URL of the SolvisRemote."""
        return f"http://{self.host}"

    async def async_get_data(self) -> SolvisData:
        """Fetch and decode the current values."""
        try:
            async with self._session.get(
                f"{self.url}{_PATH}",
                middlewares=(self._auth,),
                timeout=_TIMEOUT,
            ) as response:
                if response.status in (401, 403):
                    raise SolvisAuthError(f"authentication failed ({response.status})")
                if response.status != 200:
                    raise SolvisConnectionError(f"unexpected HTTP status {response.status}")
                document = await response.text(errors="replace")
        except (ClientError, TimeoutError) as err:
            raise SolvisConnectionError(str(err) or type(err).__name__) from err

        return parse_payload(extract_payload(document))
