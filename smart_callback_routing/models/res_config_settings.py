import secrets

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    scr_sticky_disabled = fields.Boolean(
        string='Pause sticky routing (kill switch)',
        config_parameter='smart_callback_routing.sticky_disabled',
        help='Kill switch: while active, the routing API always answers with '
             '"default" — 3CX routes normally everywhere, without touching the '
             'phone system. Outbound mappings are still recorded.',
    )
    scr_ttl_minutes = fields.Integer(
        string='Sticky TTL (minutes)',
        config_parameter='smart_callback_routing.ttl_minutes',
        default=120,
        help='Validity period of a phone-number→extension mapping. Default 120 (2 h).',
    )
    scr_first_ring_timeout = fields.Integer(
        string='First-ring timeout (seconds)',
        config_parameter='smart_callback_routing.first_ring_timeout',
        default=12,
        help='How long the preferred extension rings before the queue fallback applies.',
    )
    scr_default_country_prefix = fields.Char(
        string='Default country prefix',
        config_parameter='smart_callback_routing.default_country_prefix',
        default='49',
        help='Country prefix without "+", applied to national numbers '
             '(leading 0). Germany = 49.',
    )
    scr_skip_busy = fields.Boolean(
        string='Skip busy extension',
        config_parameter='smart_callback_routing.skip_busy',
        default=True,
    )
    scr_skip_offline = fields.Boolean(
        string='Skip offline/unregistered extension',
        config_parameter='smart_callback_routing.skip_offline',
        default=True,
    )
    scr_skip_dnd = fields.Boolean(
        string='Skip DND extension',
        config_parameter='smart_callback_routing.skip_dnd',
        default=True,
    )
    scr_logging_enabled = fields.Boolean(
        string='Log routing decisions',
        config_parameter='smart_callback_routing.logging_enabled',
        default=True,
    )
    scr_api_key = fields.Char(
        string='API key',
        config_parameter='smart_callback_routing.api_key',
        help='Sent by 3CX in the "X-API-Key" header. Only requests with the '
             'correct key are answered (SEC-001/SEC-002).',
    )
    scr_signing_secret = fields.Char(
        string='HMAC signing secret (optional)',
        config_parameter='smart_callback_routing.signing_secret',
        help='If set, requests must additionally carry an HMAC-SHA256 signature '
             'of the raw body in the "X-Signature" header (SEC-003).',
    )

    def action_scr_generate_api_key(self):
        """Generates a new random API key and stores it."""
        self.ensure_one()
        key = secrets.token_urlsafe(32)
        self.env['ir.config_parameter'].sudo().set_param(
            'smart_callback_routing.api_key', key)
        self.scr_api_key = key
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'API key generated',
                'message': 'A new API key has been generated and saved.',
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }
