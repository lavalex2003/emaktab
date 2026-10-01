"""API client for eMaktab v2 diary."""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any

import aiohttp

from .auth import EmaktabAuthManager
from .const import BASE_URL

_LOGGER = logging.getLogger(__name__)


class EmaktabApiClient:
    """Client for eMaktab API."""

    def __init__(self, auth: EmaktabAuthManager) -> None:
        self._auth = auth
        self._resolved_schools: dict[tuple[str, str], str] = {}

    @staticmethod
    def _week_range_utc(now: datetime) -> tuple[int, int]:
        """Return UTC timestamps for current week (Mon 00:00 - Sun 23:59:59)."""
        # Normalize to UTC
        now_utc = now.astimezone(timezone.utc)
        start = now_utc - timedelta(days=now_utc.weekday())
        start = start.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=6, hours=23, minutes=59, seconds=59)
        return int(start.timestamp()), int(end.timestamp())

    async def async_get_diary(
        self,
        person_id: str,
        school_id: str,
    ) -> dict[str, Any]:
        """
        Fetch diary data for the current week from v2 API.

        Returns raw JSON as provided by API.
        """
        await self._auth.ensure_logged_in()

        url = f"{BASE_URL}/api/v2/marks/diary"

        now = datetime.now(timezone.utc)
        start_ts, finish_ts = self._week_range_utc(now)
        
        # ВРЕМЕННО: фиксированная учебная дата для тестирования
        #now = datetime(2025, 11, 13, tzinfo=timezone.utc)
        #start_ts, finish_ts = self._week_range_utc(now)

        params = {
            "personId": person_id,
            "schoolId": self._resolved_schools.get((person_id, school_id), school_id),
            "startDate": start_ts,
            "finishDate": finish_ts,
            "timestamp": int(now.timestamp() * 1000),
        }

        _LOGGER.info(
            "Requesting eMaktab diary v2: person=%s, range=%s..%s",
            person_id,
            start_ts,
            finish_ts,
        )

        try:
            result = await self._async_request_diary(url, params)
            if result.get("days") == [] and (person_id, school_id) not in self._resolved_schools:
                current_school = await self._async_find_current_school(person_id, school_id)
                if current_school is not None:
                    params["schoolId"] = current_school
                    result = await self._async_request_diary(url, params)
                    self._resolved_schools[(person_id, school_id)] = current_school
                    _LOGGER.warning(
                        "Configured eMaktab school is no longer linked to this student; "
                        "using the current school from the account"
                    )
            return result
        except aiohttp.ClientError as err:
            _LOGGER.error("HTTP error during diary API request: %s", err)
            raise

    @staticmethod
    def _memberships_from_page(page: str) -> list[dict[str, Any]]:
        """Extract the memberships supplied to the website's diary."""
        marker = re.search(r'"schoolMemberships"\s*:\s*', page)
        if marker is None:
            raise ValueError("School memberships not found")
        memberships, _ = json.JSONDecoder().raw_decode(page[marker.end():])
        if not isinstance(memberships, list):
            raise ValueError("Unexpected school memberships format")
        return [
            item for item in memberships
            if isinstance(item, dict) and item.get("personId") and item.get("schoolId")
        ]

    async def async_get_memberships(self) -> list[dict[str, Any]]:
        """Discover children and schools visible to the signed-in account."""
        await self._auth.ensure_logged_in()
        async with self._auth.session.get(f"{BASE_URL}/marks") as response:
            if response.status != 200 or response.url.host != "emaktab.uz":
                raise RuntimeError("Unable to load account school memberships")
            return self._memberships_from_page(await response.text())

    @classmethod
    def _current_school_from_page(
        cls, page: str, person_id: str, configured_school: str
    ) -> str | None:
        """Resolve only an unambiguous primary school for the configured child."""
        try:
            memberships = cls._memberships_from_page(page)
        except ValueError:
            return None
        memberships = [
            item for item in memberships if str(item["personId"]) == str(person_id)
        ]
        # An empty week is normal if the configured school is still linked.
        if any(str(item.get("schoolId")) == str(configured_school) for item in memberships):
            return None
        schools = {
            str(item["schoolId"]) for item in memberships
            if item.get("isOo") is True and item.get("isOdo") is not True
            and item.get("schoolId") is not None
        }
        return next(iter(schools)) if len(schools) == 1 else None

    async def _async_find_current_school(
        self, person_id: str, configured_school: str
    ) -> str | None:
        """Read the same school memberships used by the website's diary."""
        async with self._auth.session.get(f"{BASE_URL}/marks") as response:
            if response.status != 200 or response.url.host != "emaktab.uz":
                return None
            return self._current_school_from_page(
                await response.text(), person_id, configured_school
            )

    async def _async_request_diary(
        self, url: str, params: dict[str, str | int]
    ) -> dict[str, Any]:
        """Request diary data, renewing an expired session exactly once."""
        for attempt in range(2):
            async with self._auth.session.get(
                url,
                params=params,
                allow_redirects=False,
                headers={
                    "Referer": f"{BASE_URL}/",
                },
            ) as response:
                if response.status in (401, 403) or 300 <= response.status < 400:
                    if attempt == 0:
                        _LOGGER.warning(
                            "Authorization error (%s), renewing session",
                            response.status,
                        )
                        self._auth.invalidate()
                        await self._auth.async_login()
                        continue
                    raise RuntimeError("Authorization failed after re-login")

                if response.status != 200:
                    text = await response.text()
                    _LOGGER.error(
                        "Unexpected diary API status %s, body=%s",
                        response.status,
                        text[:200],
                    )
                    raise RuntimeError(
                        f"Diary API request failed with status {response.status}"
                    )

                data = await response.json(content_type=None)
                if not isinstance(data, dict):
                    raise RuntimeError("Diary API returned an unexpected response")
                _LOGGER.debug(
                    "eMaktab diary API response received (keys: %s)",
                    list(data.keys()) if isinstance(data, dict) else type(data),
                )
                return data

        raise RuntimeError("Diary API request failed")
