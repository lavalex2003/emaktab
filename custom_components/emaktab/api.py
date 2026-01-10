"""API client for eMaktab v2 diary."""

from __future__ import annotations

import logging
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
            "schoolId": school_id,
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
            async with self._auth.session.get(
                url,
                params=params,
                headers={
                    "Referer": f"{BASE_URL}/",
                },
            ) as response:
                if response.status in (401, 403):
                    _LOGGER.warning(
                        "Authorization error (%s), retrying login",
                        response.status,
                    )
                    await self._auth.async_login()
                    raise RuntimeError("Authorization failed, re-login required")

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

                data = await response.json()
                _LOGGER.debug(
                    "eMaktab diary API response received (keys: %s)",
                    list(data.keys()) if isinstance(data, dict) else type(data),
                )
                return data

        except aiohttp.ClientError as err:
            _LOGGER.error("HTTP error during diary API request: %s", err)
            raise

        except Exception:
            _LOGGER.exception("Unexpected error during diary API request")
            raise
