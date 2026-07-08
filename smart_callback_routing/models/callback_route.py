import logging
from datetime import timedelta

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

# Default TTL used when no configuration parameter is set (minutes).
DEFAULT_TTL_MINUTES = 120


class ScrCallbackRoute(models.Model):
    """Temporary sticky mapping: phone number → 3CX extension.

    Exactly one active mapping exists per (normalized number, company).
    A new qualifying outbound attempt overwrites the existing mapping
    ("Last Outbound Wins", BR-007 / FR-006).
    """

    _name = 'scr.callback.route'
    _description = 'Smart Callback Routing – Sticky Mapping'
    _order = 'expires_at desc'
    _rec_name = 'phone_normalized'

    phone_normalized = fields.Char(
        string='Phone Number',
        required=True,
        index=True,
        help='Normalized external phone number (e.g. +491701234567).',
    )
    extension = fields.Char(
        string='Extension',
        required=True,
        index=True,
        help='3CX extension of the employee who last dialed outbound.',
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Company',
        required=True,
        index=True,
        default=lambda self: self.env.company,
        ondelete='cascade',
    )
    created_at = fields.Datetime(
        string='Created',
        required=True,
        default=fields.Datetime.now,
        readonly=True,
    )
    expires_at = fields.Datetime(
        string='Expires',
        required=True,
        index=True,
        readonly=True,
        help='Moment at which the mapping expires (end of TTL).',
    )
    last_call_id = fields.Char(
        string='Last Call ID',
        help='3CX call ID of the outbound attempt that created this mapping.',
    )
    extension_id = fields.Many2one(
        comodel_name='scr.extension',
        string='Mapped Extension',
        compute='_compute_extension_id',
        help='Linked extension record (for presence checks & transparency). '
             'Not stored — resolved on demand, because extensions may be '
             'created only after the mapping.',
    )
    active = fields.Boolean(string='Active', default=True, index=True)
    is_valid = fields.Boolean(
        string='Valid',
        compute='_compute_is_valid',
        search='_search_is_valid',
        help='True as long as the mapping is active and not expired.',
    )

    _unique_phone_company = models.Constraint(
        'UNIQUE(phone_normalized, company_id)',
        'Only one mapping may exist per phone number and company.',
    )

    @api.depends('extension', 'company_id')
    def _compute_extension_id(self):
        for route in self:
            route.extension_id = route._resolve_extension().id or False

    def _resolve_extension(self):
        """Looks up the matching ``scr.extension`` record (live, not cached).

        Robust against ordering: the extension may be created only after the
        sticky mapping (e.g. via a presence event).
        """
        self.ensure_one()
        return self.env['scr.extension'].search([
            ('name', '=', self.extension),
            ('company_id', '=', self.company_id.id),
        ], limit=1)

    @property
    def is_expired(self):
        self.ensure_one()
        return bool(self.expires_at and self.expires_at <= fields.Datetime.now())

    @api.depends('active', 'expires_at')
    def _compute_is_valid(self):
        now = fields.Datetime.now()
        for route in self:
            route.is_valid = bool(
                route.active and route.expires_at and route.expires_at > now)

    def _search_is_valid(self, operator, value):
        """Server-side validity filter.

        Deliberately NOT a static domain with ``datetime.datetime.now()`` in
        the search view: the web client evaluates such domains browser-locally,
        while ``expires_at`` is stored in UTC — the TZ offset would hide
        mappings that are still valid. Here the server compares in UTC
        (``fields.Datetime.now()``).

        Odoo internally normalizes ``('is_valid', '=', True)`` to
        ``('in', {True})``, so ``in``/``not in`` are handled like ``=``/``!=``.
        """
        if operator in ('in', 'not in'):
            wants_valid = True in value
            negate = operator == 'not in'
        elif operator in ('=', '!='):
            wants_valid = bool(value)
            negate = operator == '!='
        else:
            raise NotImplementedError(
                f'Operator {operator!r} is not supported for is_valid.')

        now = fields.Datetime.now()
        valid_domain = [('active', '=', True), ('expires_at', '>', now)]
        invalid_domain = ['|', ('active', '=', False), ('expires_at', '<=', now)]
        return invalid_domain if (wants_valid == negate) else valid_domain

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------
    @api.model
    def _get_ttl_minutes(self):
        param = self.env['ir.config_parameter'].sudo().get_param(
            'smart_callback_routing.ttl_minutes')
        try:
            value = int(param)
            return value if value > 0 else DEFAULT_TTL_MINUTES
        except (TypeError, ValueError):
            return DEFAULT_TTL_MINUTES

    # ------------------------------------------------------------------
    # Core operations (called by the controllers)
    # ------------------------------------------------------------------
    @api.model
    def register_outbound(self, phone_normalized, extension, company, call_id=None):
        """Creates or updates a sticky mapping (upsert).

        :param company: ``res.company`` recordset (exactly one).
        :return: the (new/updated) ``scr.callback.route`` record.
        """
        now = fields.Datetime.now()
        expires_at = now + timedelta(minutes=self._get_ttl_minutes())

        existing = self.search([
            ('phone_normalized', '=', phone_normalized),
            ('company_id', '=', company.id),
        ], limit=1)

        vals = {
            'extension': extension,
            'expires_at': expires_at,
            'last_call_id': call_id or False,
            'active': True,
        }
        if existing:
            # Deliberately do NOT reset created_at — "created_at" marks the
            # first contact; the expiry date, however, is extended.
            existing.write(vals)
            return existing

        vals.update({
            'phone_normalized': phone_normalized,
            'company_id': company.id,
            'created_at': now,
        })
        return self.create(vals)

    @api.model
    def find_active(self, phone_normalized, company):
        """Looks up a valid (non-expired, active) mapping.

        :return: record or empty recordset.
        """
        now = fields.Datetime.now()
        return self.search([
            ('phone_normalized', '=', phone_normalized),
            ('company_id', '=', company.id),
            ('active', '=', True),
            ('expires_at', '>', now),
        ], limit=1)

    # ------------------------------------------------------------------
    # Cleanup (cron, NFR-005 / EC-004 / GDPR)
    # ------------------------------------------------------------------
    @api.model
    def _cron_cleanup_expired(self):
        """Deletes expired mappings. Called by the cron job."""
        now = fields.Datetime.now()
        expired = self.search([('expires_at', '<=', now)])
        count = len(expired)
        if expired:
            expired.unlink()
            _logger.info('Smart Callback Routing: deleted %s expired mappings.', count)
        return count
