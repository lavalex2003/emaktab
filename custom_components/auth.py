"""Authentication manager for eMaktab."""

from __future__ import annotations

import logging
from typing import Optional

import aiohttp
from aiohttp import ClientResponse

from .const import (
    LOGIN_URL,
    BASE_URL,
    USERFEED_URL,
    COOKIE_AUTH,
    DEFAULT_USER_AGENT,
    REQUEST_TIMEOUT,
)

_LOGGER = logging.getLogger(__name__)


class EmaktabAuthManager:
    """Handle authentication and session management."""

    def __init__(self, username: str, password: str) -> None:
        self._username = username
        self._password = password
        self._session: Optional[aiohttp.ClientSession] = None

    @property
    def session(self) -> aiohttp.ClientSession:
        """Return active aiohttp session."""
        if self._session is None:
            raise RuntimeError("Session is not initialized")
        return self._session

    async def async_init_session(self) -> None:
        """Initialize aiohttp session."""
        if self._session is not None:
            return

        cookie_jar = aiohttp.CookieJar(unsafe=True)

        timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)

        self._session = aiohttp.ClientSession(
            cookie_jar=cookie_jar,
            timeout=timeout,
            headers={
                "User-Agent": DEFAULT_USER_AGENT,
            },
        )

        _LOGGER.debug("HTTP session initialized")

    async def async_login(self) -> None:
        """Perform full login flow."""
        await self.async_init_session()

        _LOGGER.info("Starting eMaktab login flow")

        # STEP 1: POST login
        response = await self._post_login()
        await self._expect_status(response, 302, "login POST")

        # STEP 2: GET base domain to receive auth cookies
        response = await self._get_base()
        await self._expect_status(response, 302, "base GET")

        if not self._has_auth_cookie():
            raise RuntimeError("Auth cookie not found after base redirect")

        # STEP 3: GET userfeed as validation
        response = await self._get_userfeed()
        await self._expect_status(response, 200, "userfeed GET")

        _LOGGER.info("eMaktab login successful")

    async def ensure_logged_in(self) -> None:
        """Ensure we have a valid authenticated session."""
        if self._session is None:
            _LOGGER.debug("No session found, logging in")
            await self.async_login()
            return

        if not self._has_auth_cookie():
            _LOGGER.warning("Auth cookie missing, re-login required")
            await self.async_login()

    def _has_auth_cookie(self) -> bool:
        """Check if auth cookie exists in cookie jar."""
        if self._session is None:
            return False

        cookies = self._session.cookie_jar.filter_cookies(BASE_URL)
        return COOKIE_AUTH in cookies

    async def _post_login(self) -> ClientResponse:
        """Send login POST request."""
        assert self._session is not None

        data = {
            "login": self._username,
            "password": self._password,
            "exceededAttempts": "False",
            "ReturnUrl": "",
            "FingerprintId": "",
            "Captcha.Input": "",
            "Captcha.Id": "",
        }

        headers = {
            "Accept": (
                "text/html,application/xhtml+xml,application/xml;"
                "q=0.9,image/avif,image/webp,image/apng,*/*;"
                "q=0.8,application/signed-exchange;v=b3;q=0.7"
            ),
            "Referer": LOGIN_URL,
        }

        _LOGGER.debug("POST login request (browser-like form)")

        return await self._session.post(
            LOGIN_URL,
            data=data,
            headers=headers,
            allow_redirects=False,
        )

    async def _get_base(self) -> ClientResponse:
        """GET base domain to complete auth cookies."""
        assert self._session is not None

        _LOGGER.debug("GET base URL")

        return await self._session.get(
            BASE_URL,
            allow_redirects=False,
        )

    async def _get_userfeed(self) -> ClientResponse:
        """GET userfeed page to validate session."""
        assert self._session is not None

        _LOGGER.debug("GET userfeed URL")

        return await self._session.get(
            USERFEED_URL,
            allow_redirects=False,
            headers={
                "Referer": BASE_URL,
            },
        )

    async def _expect_status(
        self,
        response: ClientResponse,
        expected_status: int,
        step: str,
    ) -> None:
        """Validate HTTP response status."""
        if response.status != expected_status:
            text = await response.text()
            _LOGGER.error(
                "Unexpected status during %s: %s, body=%s",
                step,
                response.status,
                text[:200],
            )
            raise RuntimeError(f"Login failed at step: {step}")

        response.release()

    async def async_close(self) -> None:
        """Close session."""
        if self._session is not None:
            await self._session.close()
            self._session = None
            _LOGGER.debug("HTTP session closed")
