from odoo import api, fields, models


class ScrRoutingLog(models.Model):
    """Log of routing decisions (NFR-004 / monitoring / US-005)."""

    _name = 'scr.routing.log'
    _description = 'Smart Callback Routing – Decision Log'
    _order = 'create_date desc'
    _rec_name = 'phone_normalized'

    event = fields.Selection(
        selection=[
            ('outbound', 'Outbound recorded'),
            ('inbound', 'Inbound lookup'),
            ('presence', 'Presence update'),
            ('error', 'Error'),
        ],
        string='Event',
        required=True,
        index=True,
    )
    phone_normalized = fields.Char(string='Phone Number', index=True)
    raw_callerid = fields.Char(string='Raw Caller ID')
    did = fields.Char(string='DID/Queue')
    extension = fields.Char(string='Extension')
    decision = fields.Selection(
        selection=[
            ('sticky_first', 'Sticky – preferred ring'),
            ('default', 'Default routing'),
            ('created', 'Mapping created/updated'),
            ('ignored', 'Ignored (anonymous/invalid)'),
            ('updated', 'Presence updated'),
            ('error', 'Error'),
        ],
        string='Decision',
        index=True,
    )
    fallback_reason = fields.Selection(
        selection=[
            ('no_match', 'No valid mapping'),
            ('expired', 'Mapping expired'),
            ('unavailable', 'Extension unavailable'),
            ('sticky_disabled', 'Sticky paused (kill switch)'),
        ],
        string='Fallback Reason',
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Company',
        ondelete='cascade',
        index=True,
    )
    latency_ms = fields.Float(string='Latency (ms)')
    detail = fields.Text(string='Details')

    @api.model
    def record(self, vals):
        """Writes a log entry if logging is enabled.

        Deliberately defensive: logging must never crash the routing hot
        path (BR-009 / NFR-002).
        """
        ICP = self.env['ir.config_parameter'].sudo()
        # get_param() returns False when the parameter was never set →
        # logging is enabled by default (only an explicit "False"/"0" disables it).
        enabled = ICP.get_param('smart_callback_routing.logging_enabled')
        if enabled not in (False, None, '') and \
                str(enabled).strip().lower() in ('0', 'false', 'no'):
            return self.browse()
        try:
            return self.sudo().create(vals)
        except Exception:  # noqa: BLE001 - logging must never block
            return self.browse()
