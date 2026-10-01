"""Configure eMaktab by discovering the account's children and schools."""
from __future__ import annotations

import logging
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME, CONF_USERNAME, CONF_PASSWORD

from .api import EmaktabApiClient
from .auth import EmaktabAuthenticationError, EmaktabAuthManager
from .const import DOMAIN, CONF_PERSON_ID, CONF_SCHOOL_ID

_LOGGER = logging.getLogger(__name__)


class EmaktabConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """One child per config entry; identifiers are discovered, not typed."""

    VERSION = 1

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}
        self._memberships: list[dict[str, Any]] = []
        self._person_id: str | None = None

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            auth = EmaktabAuthManager(user_input[CONF_USERNAME], user_input[CONF_PASSWORD])
            try:
                self._memberships = await EmaktabApiClient(auth).async_get_memberships()
            except EmaktabAuthenticationError:
                errors["base"] = "invalid_auth"
            except (aiohttp.ClientError, TimeoutError, RuntimeError, ValueError):
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error discovering eMaktab children")
                errors["base"] = "unknown"
            finally:
                await auth.async_close()
            if not errors:
                if not self._memberships:
                    errors["base"] = "no_children"
                else:
                    self._data = {
                        key: user_input[key]
                        for key in (CONF_USERNAME, CONF_PASSWORD)
                    }
                    self._person_id = None
                    return await self.async_step_child()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_USERNAME): str,
                vol.Required(CONF_PASSWORD): str,
            }),
            errors=errors,
        )

    async def async_step_child(self, user_input=None):
        children = {
            str(item["personId"]): " ".join(
                str(item.get(key) or "") for key in ("lastName", "firstName")
            ).strip() or str(item["personId"])
            for item in self._memberships
        }
        errors = {}
        if user_input is not None:
            person_id = user_input.get(CONF_PERSON_ID)
            if person_id in children:
                self._person_id = person_id
                self._data[CONF_NAME] = children[person_id]
                return await self.async_step_school()
            errors["base"] = "invalid_selection"
        elif len(children) == 1:
            self._person_id = next(iter(children))
            self._data[CONF_NAME] = children[self._person_id]
            return await self.async_step_school()
        return self.async_show_form(
            step_id="child",
            data_schema=vol.Schema({vol.Required(CONF_PERSON_ID): vol.In(children)}),
            errors=errors,
        )

    async def async_step_school(self, user_input=None):
        schools = {
            str(item["schoolId"]): item.get("schoolName") or str(item["schoolId"])
            for item in self._memberships
            if str(item["personId"]) == self._person_id
        }
        errors = {}
        school_id = None
        if user_input is not None:
            school_id = user_input.get(CONF_SCHOOL_ID)
            if school_id not in schools:
                errors["base"] = "invalid_selection"
        elif len(schools) == 1:
            school_id = next(iter(schools))
        if school_id in schools and not errors:
            # Older entries have no unique_id, so also inspect their data.
            if any(str(entry.data.get(CONF_PERSON_ID)) == self._person_id
                   for entry in self._async_current_entries()):
                return self.async_abort(reason="already_configured")
            await self.async_set_unique_id(self._person_id)
            self._abort_if_unique_id_configured()
            auth = EmaktabAuthManager(self._data[CONF_USERNAME], self._data[CONF_PASSWORD])
            try:
                result = await EmaktabApiClient(auth).async_get_diary(self._person_id, school_id)
                if not isinstance(result.get("days"), list):
                    raise ValueError("Unexpected diary format")
            except EmaktabAuthenticationError:
                errors["base"] = "invalid_auth"
            except (aiohttp.ClientError, TimeoutError, RuntimeError, ValueError):
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error validating eMaktab diary")
                errors["base"] = "unknown"
            finally:
                await auth.async_close()
            if not errors:
                return self.async_create_entry(
                    title=self._data[CONF_NAME],
                    data={**self._data, CONF_PERSON_ID: self._person_id, CONF_SCHOOL_ID: school_id},
                )
        return self.async_show_form(
            step_id="school",
            data_schema=vol.Schema({vol.Required(CONF_SCHOOL_ID): vol.In(schools)}),
            errors=errors,
        )
