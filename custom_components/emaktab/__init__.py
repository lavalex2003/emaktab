from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .api import EmaktabApiClient
from .auth import EmaktabAuthManager
from .const import DOMAIN, PLATFORMS
from .coordinator import EmaktabCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up eMaktab integration (YAML deprecated)."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up eMaktab from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    _LOGGER.info("Setting up eMaktab entry: %s", entry.title)

    auth = EmaktabAuthManager(
        entry.data["username"],
        entry.data["password"],
    )

    api = EmaktabApiClient(auth)

    coordinator = EmaktabCoordinator(
        hass=hass,
        api=api,
        person_id=entry.data["person_id"],
        school_id=entry.data["school_id"],
        group_id=entry.data.get("group_id"),
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "api": api,
        "auth": auth,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(
        entry, PLATFORMS
    )

    if unload_ok:
        data = hass.data[DOMAIN].pop(entry.entry_id, None)
        if data and "auth" in data:
            await data["auth"].async_close()

    return unload_ok
