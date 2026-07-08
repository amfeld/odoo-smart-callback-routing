from odoo import api, fields, models


class ScrExtension(models.Model):
    """3CX extension and its (optional) presence state.

    Serves two purposes:
    * Transparency/mapping extension → employee (US-005).
    * Best-effort availability check (FR-012/FR-013): if 3CX delivers
      presence events, the routing lookup can immediately skip an
      offline/DND/busy extension. If the state is unknown, the extension is
      treated as available (non-blocking — the 3CX call flow handles the
      ring-no-answer fallback).
    """

    _name = 'scr.extension'
    _description = 'Smart Callback Routing – 3CX Extension'
    _order = 'name'
    _rec_name = 'name'

    name = fields.Char(
        string='Extension',
        required=True,
        index=True,
        help='3CX extension number, e.g. 105.',
    )
    employee_id = fields.Many2one(
        comodel_name='hr.employee',
        string='Employee',
        ondelete='set null',
        help='Optional: mapped employee (informational only).',
    )
    user_id = fields.Many2one(
        comodel_name='res.users',
        string='User',
        ondelete='set null',
        help='Optional: mapped Odoo user (informational only).',
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Company',
        required=True,
        index=True,
        default=lambda self: self.env.company,
        ondelete='cascade',
    )
    presence_state = fields.Selection(
        selection=[
            ('available', 'Available'),
            ('busy', 'Busy'),
            ('dnd', 'Do Not Disturb (DND)'),
            ('offline', 'Offline'),
            ('unknown', 'Unknown'),
        ],
        string='Presence',
        default='unknown',
        required=True,
    )
    registered = fields.Boolean(
        string='Registered',
        default=True,
        help='Whether the extension\'s device is registered with 3CX.',
    )
    presence_updated_at = fields.Datetime(string='Presence Updated', readonly=True)
    active = fields.Boolean(string='Active', default=True)

    _unique_name_company = models.Constraint(
        'UNIQUE(name, company_id)',
        'An extension may exist only once per company.',
    )

    def is_available_for_routing(self):
        """True if, per the known presence, the extension may ring first.

        An unknown state counts as available (best effort, non-blocking).
        The individual skip rules can be toggled in the settings.
        """
        self.ensure_one()
        ICP = self.env['ir.config_parameter'].sudo()

        def _flag(key, default=True):
            # get_param() returns False when the parameter does NOT exist
            # (≠ explicitly set to "False") → then the default applies.
            val = ICP.get_param(f'smart_callback_routing.{key}')
            if val in (False, None, ''):
                return default
            return str(val).strip().lower() not in ('0', 'false', 'no')

        if _flag('skip_offline') and (self.presence_state == 'offline' or not self.registered):
            return False
        if _flag('skip_busy') and self.presence_state == 'busy':
            return False
        if _flag('skip_dnd') and self.presence_state == 'dnd':
            return False
        return True

    @api.model
    def update_presence(self, name, company, state=None, registered=None):
        """Upserts a presence state (called by the presence endpoint)."""
        ext = self.search([
            ('name', '=', name),
            ('company_id', '=', company.id),
        ], limit=1)
        vals = {'presence_updated_at': fields.Datetime.now()}
        if state is not None:
            vals['presence_state'] = state
        if registered is not None:
            vals['registered'] = bool(registered)
        if ext:
            ext.write(vals)
            return ext
        vals.update({'name': name, 'company_id': company.id})
        return self.create(vals)
