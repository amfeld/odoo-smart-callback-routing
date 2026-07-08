import hashlib
import hmac
import json
import logging
import time

from odoo import http
from odoo.http import request

from ..models.phone_utils import normalize_phone

_logger = logging.getLogger(__name__)

# Outbound events that may create a sticky mapping (FR-002/FR-003):
# only once ringing / a carrier attempt was reached. "failed"/"instant" does not count.
QUALIFYING_OUTBOUND_EVENTS = {'ringing', 'answered', 'busy', 'noanswer', 'no_answer'}


class SmartCallbackController(http.Controller):
    """HTTP JSON API for the 3CX integration.

    All endpoints are ``auth='public'`` and are authenticated exclusively via
    an API key (header ``X-API-Key``) — 3CX is not an Odoo user. Database
    access therefore runs through ``sudo()``.

    Principle (BR-009/NFR-002): routing never blocks. Every internal error
    results in a valid default response, not an empty 500.
    """

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _icp(self, key, default=None):
        return request.env['ir.config_parameter'].sudo().get_param(
            f'smart_callback_routing.{key}', default)

    def _authenticate(self, raw_body, payload=None):
        """Checks the API key and (optionally) the HMAC signature. Returns True/False."""
        expected_key = self._icp('api_key')
        if not expected_key:
            # Without a configured key the API is deliberately locked.
            _logger.warning('Smart Callback Routing: no API key configured — request rejected.')
            return False

        provided = request.httprequest.headers.get('X-API-Key', '')
        if not provided and payload:
            # Not every 3CX mechanism can set a custom header (e.g. the CRM
            # template call journaling). Therefore also accept the key as a
            # body/form field.
            provided = payload.get('apikey') or ''
        if not hmac.compare_digest(str(provided), str(expected_key)):
            return False

        secret = self._icp('signing_secret')
        if secret:
            signature = request.httprequest.headers.get('X-Signature', '')
            digest = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
            if not hmac.compare_digest(str(signature), digest):
                return False
        return True

    def _company_for(self, payload, extension=None):
        """Determines the company for a request.

        Order: explicit ``company_id`` in the payload → company of the known
        extension → default company (lowest ID).
        """
        company_id = payload.get('company_id')
        if company_id:
            company = request.env['res.company'].sudo().browse(int(company_id)).exists()
            if company:
                return company
        if extension:
            ext = request.env['scr.extension'].sudo().search(
                [('name', '=', str(extension))], limit=1)
            if ext:
                return ext.company_id
        return request.env['res.company'].sudo().search([], order='id', limit=1)

    def _country_prefix(self):
        return self._icp('default_country_prefix') or '49'

    def _json(self, data, status=200):
        return request.make_json_response(data, status=status)

    def _read_payload(self, kwargs=None):
        """Reads the request body as JSON; falls back to form fields (kwargs).

        The 3CX CRM template call journaling may send the body URL-encoded
        instead of as JSON — it then ends up in ``kwargs`` (``type='http'``
        route). In that case we use the form fields as payload.
        """
        raw = request.httprequest.get_data() or b''
        try:
            payload = json.loads(raw.decode('utf-8')) if raw else {}
        except (ValueError, UnicodeDecodeError):
            payload = {}
        if not isinstance(payload, dict):
            payload = {}
        if not payload and kwargs:
            payload = dict(kwargs)
        return raw, payload

    # ------------------------------------------------------------------
    # 1) Outbound recording  → create/update sticky mapping
    # ------------------------------------------------------------------
    @http.route('/api/3cx/outbound', type='http', auth='public',
                methods=['POST'], csrf=False, save_session=False)
    def outbound(self, **kwargs):
        raw, payload = self._read_payload(kwargs)
        if not self._authenticate(raw, payload):
            return self._json({'error': 'unauthorized'}, status=401)

        Log = request.env['scr.routing.log'].sudo()
        try:
            # Event directly (`event`) or from the CRM journaling field (`calltype`).
            event = str(payload.get('event') or payload.get('calltype') or 'ringing').strip().lower()
            # Map 3CX CallType values (Outbound/Notanswered) and spelling
            # variants to qualifying events. Both create a sticky mapping.
            event = {
                'outbound': 'answered',
                'notanswered': 'noanswer', 'no answer': 'noanswer',
                'not answered': 'noanswer', 'unanswered': 'noanswer', 'missed': 'noanswer',
            }.get(event, event)
            extension = str(payload.get('extension', '')).strip()
            raw_number = payload.get('number') or payload.get('callee') or payload.get('callerid')
            call_id = payload.get('call_id') or payload.get('callid')

            if event not in QUALIFYING_OUTBOUND_EVENTS or not extension:
                Log.record({
                    'event': 'outbound', 'decision': 'ignored', 'extension': extension,
                    'raw_callerid': raw_number, 'detail': f'Event "{event}" is not qualifying.',
                })
                return self._json({'status': 'ignored', 'reason': 'non_qualifying_event'})

            phone = normalize_phone(raw_number, self._country_prefix())
            if not phone:
                Log.record({
                    'event': 'outbound', 'decision': 'ignored', 'extension': extension,
                    'raw_callerid': raw_number, 'detail': 'Anonymous/invalid number.',
                })
                return self._json({'status': 'ignored', 'reason': 'invalid_number'})

            company = self._company_for(payload, extension=extension)
            route = request.env['scr.callback.route'].sudo().register_outbound(
                phone, extension, company, call_id=call_id)

            Log.record({
                'event': 'outbound', 'decision': 'created', 'phone_normalized': phone,
                'raw_callerid': raw_number, 'extension': extension,
                'company_id': company.id,
                'detail': f'Mapping until {route.expires_at} (call {call_id or "-"}).',
            })
            return self._json({
                'status': 'ok',
                'phone': phone,
                'extension': extension,
                'expires_at': route.expires_at.isoformat(),
            })
        except Exception as exc:  # noqa: BLE001 - never block
            _logger.exception('Smart Callback Routing: outbound processing failed.')
            Log.record({'event': 'error', 'decision': 'error', 'detail': str(exc)})
            return self._json({'status': 'error'}, status=200)

    # ------------------------------------------------------------------
    # 2) Presence update
    # ------------------------------------------------------------------
    @http.route('/api/3cx/presence', type='http', auth='public',
                methods=['POST'], csrf=False, save_session=False)
    def presence(self, **kwargs):
        raw, payload = self._read_payload(kwargs)
        if not self._authenticate(raw, payload):
            return self._json({'error': 'unauthorized'}, status=401)

        try:
            extension = str(payload.get('extension', '')).strip()
            if not extension:
                return self._json({'status': 'ignored', 'reason': 'no_extension'})

            state = payload.get('state')
            if state is not None:
                state = str(state).strip().lower()
                valid = {'available', 'busy', 'dnd', 'offline', 'unknown'}
                if state not in valid:
                    state = 'unknown'
            registered = payload.get('registered')

            company = self._company_for(payload, extension=extension)
            request.env['scr.extension'].sudo().update_presence(
                extension, company, state=state, registered=registered)

            request.env['scr.routing.log'].sudo().record({
                'event': 'presence', 'decision': 'updated', 'extension': extension,
                'company_id': company.id,
                'detail': f'state={state}, registered={registered}',
            })
            return self._json({'status': 'ok'})
        except Exception as exc:  # noqa: BLE001
            _logger.exception('Smart Callback Routing: presence processing failed.')
            return self._json({'status': 'error'}, status=200)

    # ------------------------------------------------------------------
    # 3) Inbound routing lookup  (hot path, target < 50 ms)
    # ------------------------------------------------------------------
    @http.route('/api/3cx/callback-routing', type='http', auth='public',
                methods=['POST'], csrf=False, save_session=False)
    def callback_routing(self, **kwargs):
        start = time.monotonic()
        raw, payload = self._read_payload(kwargs)
        if not self._authenticate(raw, payload):
            return self._json({'error': 'unauthorized'}, status=401)

        Log = request.env['scr.routing.log'].sudo()
        try:
            raw_callerid = payload.get('callerid')
            did = payload.get('did') or payload.get('queue')
            phone = normalize_phone(raw_callerid, self._country_prefix())
            company = self._company_for(payload)

            def _log(decision, fallback_reason=None, extension=None, detail=None):
                Log.record({
                    'event': 'inbound', 'decision': decision,
                    'fallback_reason': fallback_reason,
                    'phone_normalized': phone, 'raw_callerid': raw_callerid,
                    'did': did, 'extension': extension, 'company_id': company.id,
                    'latency_ms': round((time.monotonic() - start) * 1000, 2),
                    'detail': detail,
                })

            # Global kill switch (settings): pause server-side without
            # touching 3CX. Stored inverted (sticky_disabled) because
            # set_param deletes False values — a missing parameter must mean
            # "active".
            if str(self._icp('sticky_disabled') or '').strip().lower() in ('true', '1'):
                _log('default', fallback_reason='sticky_disabled')
                return self._json({'mode': 'default'})

            # Anonymous/invalid number → default (EC-006).
            if not phone:
                _log('default', fallback_reason='no_match', detail='Anonymous/invalid caller ID.')
                return self._json({'mode': 'default'})

            route = request.env['scr.callback.route'].sudo().find_active(phone, company)
            if not route:
                _log('default', fallback_reason='no_match')
                return self._json({'mode': 'default'})

            # Check extension availability (FR-012/FR-013), best effort.
            # Live lookup, because the extension may have been created only
            # after the mapping (e.g. via a presence event).
            ext_rec = route.sudo()._resolve_extension()
            if ext_rec and not ext_rec.is_available_for_routing():
                _log('default', fallback_reason='unavailable', extension=route.extension)
                return self._json({'mode': 'default'})

            # Timeout & fallback queue (informational; the call processing
            # script does not enforce either — see docs/3cx_cfd/README.md).
            timeout = int(self._icp('first_ring_timeout') or 12)
            fallback = payload.get('queue') or (str(did) if did else None)

            _log('sticky_first', extension=route.extension)
            response = {
                'mode': 'sticky_first',
                'extension': route.extension,
                'timeout': timeout,
            }
            if fallback:
                response['fallback'] = fallback
            return self._json(response)
        except Exception as exc:  # noqa: BLE001 - never block → default
            _logger.exception('Smart Callback Routing: routing lookup failed.')
            Log.record({'event': 'error', 'decision': 'error', 'detail': str(exc)})
            return self._json({'mode': 'default'}, status=200)
