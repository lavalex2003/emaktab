"""DataUpdateCoordinator for eMaktab integration (v2 diary)."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .api import EmaktabApiClient
from .const import DOMAIN, DEFAULT_SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)


class EmaktabCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator to manage eMaktab data updates."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: EmaktabApiClient,
        person_id: str,
        school_id: str,
        group_id: str,
        scan_interval: int = DEFAULT_SCAN_INTERVAL,
    ) -> None:
        self._api = api
        self._person_id = person_id
        self._school_id = school_id
        self._group_id = group_id  # пока не используется в v2 diary

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=None,  # интервал уже задан ранее через timedelta в предыдущих правках
        )

        # Хранилище состояния
        self.data = {
            "days": [],
            "last_update": None,
            "error": None,
        }

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch diary data from v2 API."""
        now = datetime.now(timezone.utc).astimezone()

        try:
            _LOGGER.info("Updating eMaktab diary data (v2)")

            result = await self._api.async_get_diary(
                person_id=self._person_id,
                school_id=self._school_id,
            )

            # Ожидаем структуру: { "days": [...] }
            days = result.get("days", []) if isinstance(result, dict) else []

            self.data["days"] = days
            self.data["last_update"] = now.isoformat()
            self.data["error"] = None

            _LOGGER.debug(
                "eMaktab diary updated: days_count=%s",
                len(days),
            )

            return self.data

        except Exception as err:
            self.data["error"] = str(err)
            _LOGGER.error("Failed to update eMaktab diary data: %s", err)
            raise UpdateFailed(str(err)) from err
