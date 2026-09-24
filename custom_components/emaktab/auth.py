"""Authentication manager for eMaktab."""

from __future__ import annotations

import logging
from html.parser import HTMLParser
from typing import Optional
from urllib.parse import urljoin

import aiohttp

from .const import DEFAULT_USER_AGENT, LOGIN_URL, REQUEST_TIMEOUT, USERFEED_URL

_LOGGER = logging.getLogger(__name__)


class EmaktabAuthenticationError(RuntimeError):
    """Raised when eMaktab rejects the supplied credentials."""


class _LoginFormParser(HTMLParser):
    """Extract the login form action and hidden fields without extra dependencies."""

    def __init__(self, base_url: str = LOGIN_URL) -> None:
        super().__init__()
        self._base_url = base_url
        self.action = base_url
        self.hidden: dict[str, str] = {}
        self._in_form = False
        self._form_action = base_url
        self._form_hidden: dict[str, str] = {}
        self._has_password = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "form":
            self._in_form = True
            self._form_action = self._base_url
            self._form_hidden = {}
            self._has_password = False
            if values.get("action"):
                self._form_action = urljoin(self._base_url, values["action"])
        elif tag == "input" and self._in_form:
            name = values.get("name")
            if name and values.get("type", "").lower() == "hidden":
                self._form_hidden[name] = values.get("value") or ""
            if values.get("type", "").lower() == "password":
                self._has_password = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "form" and self._in_form:
            if self._has_password:
                self.action = self._form_action
                self.hidden = self._form_hidden
            self._in_form = False


class EmaktabAuthManager:
    """Handle authentication and session management."""

    def __init__(self, username: str, password: str) -> None:
        self._username = username
        self._password = password
        self._session: Optional[aiohttp.ClientSession] = None
        self._authenticated = False

    @property
    def session(self) -> aiohttp.ClientSession:
        """Return active aiohttp session."""
        if self._session is None:
            raise RuntimeError("Session is not initialized")
        return self._session

    async def async_init_session(self) -> None:
        """Initialize aiohttp session."""
        if self._session is not None and not self._session.closed:
            return

        self._session = aiohttp.ClientSession(
            cookie_jar=aiohttp.CookieJar(unsafe=True),
            timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT),
            headers={"User-Agent": DEFAULT_USER_AGENT},
        )

    async def async_login(self) -> None:
        """Perform the browser login flow and validate the resulting session.

        eMaktab now serves an anti-forgery value on the login page and no longer
        guarantees the old sequence of two 302 responses.  Fetch and submit the
        current form and let aiohttp follow the service's redirects instead of
        depending on those implementation details.
        """
        await self.async_init_session()
        self._authenticated = False
        self.session.cookie_jar.clear()

        _LOGGER.info("Starting eMaktab login flow")
        async with self.session.get(LOGIN_URL) as response:
            if response.status != 200:
                raise RuntimeError(f"Login page returned status {response.status}")
            parser = _LoginFormParser(str(response.url))
            parser.feed(await response.text())

        data = {
            **parser.hidden,
            "login": self._username,
            "password": self._password,
            "exceededAttempts": "False",
            "ReturnUrl": parser.hidden.get("ReturnUrl", ""),
            "FingerprintId": parser.hidden.get("FingerprintId", ""),
            "Captcha.Input": "",
            "Captcha.Id": parser.hidden.get("Captcha.Id", ""),
        }
        headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Origin": f"{LOGIN_URL.split('/login', 1)[0]}",
            "Referer": LOGIN_URL,
        }
        async with self.session.post(
            parser.action, data=data, headers=headers, allow_redirects=True
        ) as response:
            await response.read()
            if response.status >= 400:
                raise RuntimeError(f"Login request returned status {response.status}")

        # The cookie name and redirect status are service implementation details.
        # A protected page is the authoritative test of whether login succeeded.
        async with self.session.get(USERFEED_URL, allow_redirects=True) as response:
            await response.read()
            final_host = response.url.host or ""
            if response.status in (401, 403) or final_host.startswith("login."):
                raise EmaktabAuthenticationError("Invalid eMaktab credentials")
            if response.status != 200:
                raise RuntimeError(
                    f"Session validation returned status {response.status}"
                )

        self._authenticated = True
        _LOGGER.info("eMaktab login successful")

    async def ensure_logged_in(self) -> None:
        """Ensure we have an authenticated session."""
        if not self._authenticated or self._session is None or self._session.closed:
            await self.async_login()

    def invalidate(self) -> None:
        """Mark the current session as expired."""
        self._authenticated = False

    async def async_close(self) -> None:
        """Close session."""
        if self._session is not None:
            await self._session.close()
            self._session = None
        self._authenticated = False
