"""Isolated flow tests with a minimal HA harness; requires aiohttp and voluptuous.

Run: python -m unittest discover -s tests/emaktab
"""
import importlib
import json
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import AsyncMock, patch

# Avoid loading Home Assistant itself or the integration's setup module.
PACKAGE = 'emaktab_flow_test'
package = types.ModuleType(PACKAGE)
package.__path__ = [str(Path(__file__).resolve().parents[2] / 'custom_components/emaktab')]
sys.modules[PACKAGE] = package


class FlowHarness:
    def __init_subclass__(cls, **kwargs):
        pass

    def async_show_form(self, **kwargs):
        return {'type': 'form', **kwargs}

    def async_create_entry(self, **kwargs):
        return {'type': 'create_entry', **kwargs}

    def async_abort(self, **kwargs):
        return {'type': 'abort', **kwargs}

    def _async_current_entries(self):
        return getattr(self, 'existing', [])

    async def async_set_unique_id(self, value):
        self.unique_id = value

    def _abort_if_unique_id_configured(self):
        pass


ha = types.ModuleType('homeassistant')
ha.config_entries = types.SimpleNamespace(ConfigFlow=FlowHarness)
constants = types.ModuleType('homeassistant.const')
constants.CONF_NAME = 'name'
constants.CONF_USERNAME = 'username'
constants.CONF_PASSWORD = 'password'
with patch.dict(sys.modules, {'homeassistant': ha, 'homeassistant.const': constants}):
    flow_module = importlib.import_module(f'{PACKAGE}.config_flow')
api = importlib.import_module(f'{PACKAGE}.api')


def membership(person='child1', school='school1'):
    return {'personId': person, 'schoolId': school, 'firstName': person,
            'lastName': 'Test', 'schoolName': school, 'isOo': True}


class ConfigFlowTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.auth = types.SimpleNamespace(async_close=AsyncMock())
        self.client = types.SimpleNamespace(
            async_get_memberships=AsyncMock(return_value=[membership()]),
            async_get_diary=AsyncMock(return_value={'days': []}),
        )
        self.auth_patch = patch.object(flow_module, 'EmaktabAuthManager', return_value=self.auth)
        self.api_patch = patch.object(flow_module, 'EmaktabApiClient', return_value=self.client)
        self.auth_patch.start()
        self.api_patch.start()
        self.addCleanup(self.auth_patch.stop)
        self.addCleanup(self.api_patch.stop)
        self.flow = flow_module.EmaktabConfigFlow()
        self.credentials = {'username': 'parent', 'password': 'test'}

    async def test_initial_form_has_no_identifiers(self):
        result = await self.flow.async_step_user()
        self.assertEqual(set(result['data_schema'].schema), set(self.credentials))

    async def test_single_child_auto_selected_and_empty_week_valid(self):
        result = await self.flow.async_step_user(self.credentials)
        self.assertEqual(result['type'], 'create_entry')
        self.assertEqual(result['data'], dict(self.credentials, name='Test child1', person_id='child1', school_id='school1'))
        self.assertEqual(result['title'], 'Test child1')
        self.assertEqual(self.auth.async_close.await_count, 2)

    async def test_multiple_children_and_schools(self):
        self.client.async_get_memberships.return_value = [
            membership(), membership('child2', 'school2'), membership('child2', 'school3')]
        result = await self.flow.async_step_user(self.credentials)
        self.assertEqual(result['step_id'], 'child')
        result = await self.flow.async_step_child({'person_id': 'child2'})
        self.assertEqual(result['step_id'], 'school')
        result['data_schema']({'school_id': 'school3'})
        result = await self.flow.async_step_school({'school_id': 'school3'})
        self.assertEqual(result['data']['person_id'], 'child2')
        self.assertEqual(result['data']['school_id'], 'school3')
        self.assertEqual(result['title'], 'Test child2')
        self.assertEqual(result['data']['name'], 'Test child2')

    async def test_no_memberships(self):
        self.client.async_get_memberships.return_value = []
        result = await self.flow.async_step_user(self.credentials)
        self.assertEqual(result['errors']['base'], 'no_children')
        self.auth.async_close.assert_awaited_once()

    async def test_invalid_auth_and_connection(self):
        for error, expected in [(flow_module.EmaktabAuthenticationError(), 'invalid_auth'),
                                (TimeoutError(), 'cannot_connect')]:
            self.client.async_get_memberships.side_effect = error
            result = await self.flow.async_step_user(self.credentials)
            self.assertEqual(result['errors']['base'], expected)
        self.assertEqual(self.auth.async_close.await_count, 2)

    async def test_legacy_duplicate(self):
        self.flow.existing = [types.SimpleNamespace(data={'person_id': 'child1', 'school_id': 'old'})]
        result = await self.flow.async_step_user(self.credentials)
        self.assertEqual(result['reason'], 'already_configured')
        self.client.async_get_diary.assert_not_awaited()

    async def test_invalid_school_and_retry_after_network_error(self):
        self.client.async_get_memberships.return_value = [membership(), membership(school='school2')]
        await self.flow.async_step_user(self.credentials)
        result = await self.flow.async_step_school({'school_id': 'unrelated'})
        self.assertEqual(result['errors']['base'], 'invalid_selection')
        self.client.async_get_diary.assert_not_awaited()
        self.client.async_get_diary.side_effect = TimeoutError()
        result = await self.flow.async_step_school({'school_id': 'school2'})
        self.assertEqual(result['errors']['base'], 'cannot_connect')
        self.client.async_get_diary.side_effect = None
        result = await self.flow.async_step_school({'school_id': 'school2'})
        self.assertEqual(result['type'], 'create_entry')

    async def test_invalid_child(self):
        self.client.async_get_memberships.return_value = [membership(), membership('child2')]
        await self.flow.async_step_user(self.credentials)
        result = await self.flow.async_step_child({'person_id': 'unrelated'})
        self.assertEqual(result['errors']['base'], 'invalid_selection')

    def test_membership_parser(self):
        page = 'bootstrap = ' + json.dumps({'schoolMemberships': [membership(), None, {}]})
        self.assertEqual(api.EmaktabApiClient._memberships_from_page(page), [membership()])
        for page in ('maintenance', '"schoolMemberships":null'):
            with self.assertRaises(ValueError):
                api.EmaktabApiClient._memberships_from_page(page)
