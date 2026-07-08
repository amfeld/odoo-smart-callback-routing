import json

from odoo.tests import common, tagged


@tagged('post_install', '-at_install')
class TestCallbackRoutingApi(common.HttpCase):
    """End-to-end tests for POST /api/3cx/callback-routing.

    Covers the 2.0 kill switch (smart_callback_routing.sticky_disabled), which
    replaced the removed per-DID gating, plus auth and the sticky/default
    response shape — none of which the model-level tests exercise.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.Route = cls.env['scr.callback.route']
        cls.ICP = cls.env['ir.config_parameter'].sudo()
        cls.phone = '+491701234567'
        cls.api_key = 'test-scr-key'
        cls.ICP.set_param('smart_callback_routing.api_key', cls.api_key)

    def _post(self, callerid, api_key=None):
        return self.url_open(
            '/api/3cx/callback-routing',
            data=json.dumps({'callerid': callerid, 'did': '+49891234500'}),
            headers={
                'Content-Type': 'application/json',
                'X-API-Key': self.api_key if api_key is None else api_key,
            },
        )

    def test_sticky_hit(self):
        self.Route.register_outbound(self.phone, '105', self.company)
        resp = self._post(self.phone)
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body.get('mode'), 'sticky_first')
        self.assertEqual(body.get('extension'), '105')

    def test_kill_switch_forces_default(self):
        """Kill switch wins even over a valid mapping; toggling it back restores sticky."""
        self.Route.register_outbound(self.phone, '105', self.company)

        # Paused ('True'/'1' both count) -> default despite a valid mapping.
        self.ICP.set_param('smart_callback_routing.sticky_disabled', 'True')
        self.assertEqual(self._post(self.phone).json().get('mode'), 'default')

        # Off = parameter deleted (mirrors the settings toggle) -> sticky again.
        self.ICP.set_param('smart_callback_routing.sticky_disabled', False)
        self.assertEqual(self._post(self.phone).json().get('mode'), 'sticky_first')

    def test_no_mapping_returns_default(self):
        self.assertEqual(self._post('+499999999999').json().get('mode'), 'default')

    def test_wrong_api_key_unauthorized(self):
        resp = self._post(self.phone, api_key='wrong-key')
        self.assertEqual(resp.status_code, 401)
