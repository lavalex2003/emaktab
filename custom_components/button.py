from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities,
) -> None:
    """Set up the global eMaktab update button.

    Кнопка создаётся ОДИН РАЗ, независимо от количества детей.
    """
    # Создаём кнопку только для ПЕРВОЙ записи
    # чтобы не дублировать entity
    if entry.entry_id != list(hass.data[DOMAIN].keys())[0]:
        return

    async_add_entities([EmaktabUpdateAllButton(hass)], update_before_add=True)


class EmaktabUpdateAllButton(ButtonEntity):
    """Button to update all eMaktab coordinators."""

    _attr_name = "Update eMaktab Data"
    _attr_icon = "mdi:refresh"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_has_entity_name = True
    _attr_unique_id = "emaktab_update_all"

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    async def async_press(self) -> None:
        """Handle the button press."""
        _LOGGER.info("Manual eMaktab update triggered (all entries)")

        domain_data: dict[str, Any] = self.hass.data.get(DOMAIN, {})

        for entry_id, data in domain_data.items():
            coordinator = data.get("coordinator")
            if not coordinator:
                continue

            try:
                await coordinator.async_request_refresh()
                _LOGGER.debug(
                    "eMaktab data refreshed for entry %s",
                    entry_id,
                )
            except Exception as err:
                _LOGGER.error(
                    "Failed to refresh eMaktab data for entry %s: %s",
                    entry_id,
                    err,
                )
