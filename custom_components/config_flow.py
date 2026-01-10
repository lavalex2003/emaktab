from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME, CONF_USERNAME, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .api import EmaktabApiClient
from .auth import EmaktabAuthManager
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

CONF_PERSON_ID = "person_id"
CONF_SCHOOL_ID = "school_id"


class EmaktabConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for eMaktab."""

    VERSION = 1

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ):
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                await self._validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected error during eMaktab config flow")
                errors["base"] = "unknown"
            else:
                # Один ребёнок = один ConfigEntry
                return self.async_create_entry(
                    title=user_input[CONF_NAME],
                    data=user_input,
                )

        data_schema = vol.Schema(
            {
                vol.Required(CONF_NAME): str,
                vol.Required(CONF_USERNAME): str,
                vol.Required(CONF_PASSWORD): str,
                vol.Required(CONF_PERSON_ID): str,
                vol.Required(CONF_SCHOOL_ID): str,
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )

    async def _validate_input(
        self,
        hass: HomeAssistant,
        data: dict[str, Any],
    ) -> None:
        """Validate user input by logging in and doing a test API call."""
        auth = EmaktabAuthManager(
            data[CONF_USERNAME],
            data[CONF_PASSWORD],
        )
        await auth.async_login()

        api = EmaktabApiClient(auth)

        # Минимальная проверка — дергаем diary
        result = await api.async_get_diary(
            person_id=data[CONF_PERSON_ID],
            school_id=data[CONF_SCHOOL_ID],
        )

        if not isinstance(result, dict) or "days" not in result:
            raise CannotConnect

        await auth.async_close()


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
