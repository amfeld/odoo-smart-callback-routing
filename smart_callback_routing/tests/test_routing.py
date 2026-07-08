from datetime import timedelta

from odoo import fields
from odoo.tests import common, tagged


@tagged('post_install', '-at_install')
class TestSmartCallbackRouting(common.TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.Route = cls.env['scr.callback.route']
        cls.Extension = cls.env['scr.extension']
        cls.phone = '+491701234567'

    def test_register_outbound_creates_mapping(self):
        route = self.Route.register_outbound(self.phone, '105', self.company, call_id='C1')
        self.assertTrue(route)
        self.assertEqual(route.extension, '105')
        self.assertEqual(route.company_id, self.company)
        self.assertGreater(route.expires_at, fields.Datetime.now())

    def test_last_outbound_wins(self):
        first = self.Route.register_outbound(self.phone, '105', self.company)
        second = self.Route.register_outbound(self.phone, '106', self.company)
        # Same record (upsert), extension overwritten (BR-007 / FR-006).
        self.assertEqual(first, second)
        self.assertEqual(second.extension, '106')
        self.assertEqual(
            self.Route.search_count([('phone_normalized', '=', self.phone)]), 1)

    def test_find_active_returns_match(self):
        self.Route.register_outbound(self.phone, '105', self.company)
        found = self.Route.find_active(self.phone, self.company)
        self.assertTrue(found)
        self.assertEqual(found.extension, '105')

    def test_expired_mapping_not_found(self):
        route = self.Route.register_outbound(self.phone, '105', self.company)
        route.expires_at = fields.Datetime.now() - timedelta(minutes=1)
        self.assertFalse(self.Route.find_active(self.phone, self.company))

    def test_cleanup_removes_expired(self):
        route = self.Route.register_outbound(self.phone, '105', self.company)
        route.expires_at = fields.Datetime.now() - timedelta(minutes=1)
        deleted = self.Route._cron_cleanup_expired()
        self.assertGreaterEqual(deleted, 1)
        self.assertFalse(route.exists())

    def test_register_reactivates_archived_mapping(self):
        # Regression: an archived (active=False) mapping must be reactivated by a
        # new outbound, not blocked by the UNIQUE(phone, company) constraint.
        route = self.Route.register_outbound(self.phone, '105', self.company)
        route.active = False
        again = self.Route.register_outbound(self.phone, '106', self.company)
        self.assertEqual(again, route)          # same row, no constraint violation
        self.assertTrue(again.active)           # reactivated
        self.assertEqual(again.extension, '106')
        self.assertEqual(
            self.Route.with_context(active_test=False).search_count(
                [('phone_normalized', '=', self.phone)]), 1)

    def test_cleanup_removes_archived_expired(self):
        route = self.Route.register_outbound(self.phone, '105', self.company)
        route.write({'active': False,
                     'expires_at': fields.Datetime.now() - timedelta(minutes=1)})
        self.Route._cron_cleanup_expired()
        self.assertFalse(route.with_context(active_test=False).exists())

    def test_extension_link_computed(self):
        ext = self.Extension.create({'name': '105', 'company_id': self.company.id})
        route = self.Route.register_outbound(self.phone, '105', self.company)
        self.assertEqual(route.extension_id, ext)

    def test_availability_skip_offline(self):
        self.env['ir.config_parameter'].sudo().set_param(
            'smart_callback_routing.skip_offline', '1')
        ext = self.Extension.create({
            'name': '105', 'company_id': self.company.id,
            'presence_state': 'offline', 'registered': False,
        })
        self.assertFalse(ext.is_available_for_routing())

    def test_availability_skip_offline_default_when_param_unset(self):
        # Regression: get_param() returns False for a missing parameter →
        # the default (True/skip) must apply, NOT count as "disabled".
        self.env['ir.config_parameter'].sudo().search(
            [('key', '=', 'smart_callback_routing.skip_offline')]).unlink()
        ext = self.Extension.create({
            'name': '108', 'company_id': self.company.id,
            'presence_state': 'offline', 'registered': False,
        })
        self.assertFalse(ext.is_available_for_routing())

    def test_availability_unknown_is_available(self):
        ext = self.Extension.create({
            'name': '107', 'company_id': self.company.id,
            'presence_state': 'unknown',
        })
        self.assertTrue(ext.is_available_for_routing())

    def test_update_presence_upsert(self):
        ext1 = self.Extension.update_presence('200', self.company, state='busy')
        self.assertEqual(ext1.presence_state, 'busy')
        ext2 = self.Extension.update_presence('200', self.company, state='available')
        self.assertEqual(ext1, ext2)
        self.assertEqual(ext2.presence_state, 'available')
