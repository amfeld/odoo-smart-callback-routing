# Changelog

All notable changes to `smart_callback_routing` are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) · versioning
follows the Odoo manifest (`19.0.major.minor.patch`).

---

## [19.0.2.0.0]

### Added
- **Global kill switch in the settings** ("Pause sticky routing"): pauses sticky
  routing server-side — the routing API immediately answers `{"mode": "default"}`
  without any change on the 3CX side. Outbound mappings are still recorded.
  Deliberately stored inverted as `smart_callback_routing.sticky_disabled`:
  `set_param` deletes False values, and a missing parameter must mean "active".

### Removed
- **Model `scr.did.config` (DID/queue configuration) removed completely** (incl.
  menu, views, ACL, record rule). Rationale: in the productive
  call-processing-script mode, `first_ring_timeout`/`fallback_queue` had no
  effect anyway (the script only hands over; no-answer/busy fallback is handled
  by the extension's 3CX forwarding rules), and DID scoping is done by the
  `OnlyDidSuffix` filter in the inbound script. The DID gating is replaced by
  the global kill switch. `timeout`/`fallback` in the API response now come
  from the settings or the request payload (`queue`/`did`).

### Tests
- Added `tests/test_controller.py` (`HttpCase`) covering the kill switch
  end-to-end via `POST /api/3cx/callback-routing`: sticky hit, kill switch
  forcing `default` despite a valid mapping and restoring on toggle-off,
  no-mapping default, and 401 on a wrong API key. Suite: 22 tests, green on
  Odoo 19 Community **and** Enterprise.

### Fixed
- Removed a meaningless `ondelete='set null'` from the non-stored computed
  `extension_id` (had no DB column/FK).
- Aligned the `default_country_prefix` field help with the settings view.

### Documentation
- **Shared 3CX CRM template** now also lives in this module
  (`docs/3cx_cfd/3cx_odoo_v20.xml`, identical to `3cxcrm/upload_on_3cx_pbx/`).
  It serves both modules: `apikey` → contact lookup (3cxcrm), `scrapikey` →
  outbound journaling for this module. The unused key may stay empty.
  Template v4: `SkipIf` word comparisons without quotes
  (`[CallType]==Inbound`), otherwise the journaling wrongly fires on inbound too.
- Effectiveness matrix (Odoo vs. 3CX control), kill switch and DID filter
  documented in `docs/3cx_cfd/README.md`; `CONFIG_GUIDE` slimmed down accordingly.
- English source strings (Odoo i18n standard) with a German `i18n/de.po`;
  German user manual in `doc/benutzerhandbuch.md`. Published as an
  open-source module (`README.md`, `LICENSE` — AGPL-3).

---

## [19.0.1.0.6]

### Changed
- **Outbound recording now via CRM template call journaling** instead of a
  call processing script: the `3cxcrm` template reports outgoing calls via a
  `ReportCall` scenario to `/api/3cx/outbound` (does not interfere with the call).
- `POST /api/3cx/outbound` (and `/presence`, `/callback-routing`) now accept
  **URL-encoded form payloads** (fallback to form fields) and the API key
  additionally as body/form field `apikey` — necessary because the CRM
  journaling cannot always set custom headers. `hmac.compare_digest` and the
  non-blocking behavior remain unchanged.
- 3CX `CallType` values (`Outbound`→`answered`, `Notanswered`→`noanswer`) are
  mapped server-side to qualifying events.

### Documentation
- `docs/3cx_cfd/`: switched to **Call Processing Scripts** (C# directly in the
  console) — the external Call Flow Designer ZIP route is appendix-only now.
  Inbound script `SmartCallbackRouting.cs`: diagnostics log (`TRIGGER fired`)
  as the first line, strict `is ExternalLine` guard removed (it silently bailed
  out in some V20 builds). Clear separation of inbound script (trigger "call on
  a trunk") vs. outbound (journaling); dial-code outbound script marked as
  alternative/deprecated.

> **Note:** The 3CX Call Control API is **Enterprise-only** and not an option
> for the Professional edition; hence the call-processing-script approach.

---

## [19.0.1.0.5]

### Fixed
- The filter "Valid (not expired)" in *Active Callback Mappings* hid mappings
  that were still valid. Cause: the domain used `datetime.datetime.now()`,
  which the web client evaluates **browser-locally**, while `expires_at` is
  stored in UTC (Odoo standard) — the TZ offset (e.g. +2 h) ≈ TTL. Now handled
  via a searchable field `is_valid` with a server-side UTC comparison. The list
  decoration also uses `is_valid` instead of the client-side `current_date`
  comparison.

---

## [19.0.1.0.4]

### Changed
- The API key in the settings is now copyable: the field uses the
  `CopyClipboardChar` widget (with copy button) instead of the masked
  `password` display.

---

## [19.0.1.0.1]

Current functional state (documentation baseline, recorded 2026-06-03):

- Temporary callback affinity routing between 3CX and Odoo (TTL-based, non-blocking).
- HTTP JSON API: `POST /api/3cx/outbound`, `/api/3cx/presence`, `/api/3cx/callback-routing`
  (auth via `X-API-Key`, optional HMAC signature `X-Signature`).
- Models `scr.callback.route`, `scr.extension`, `scr.did.config`, `scr.routing.log`.
- "Last Outbound Wins" upsert, sticky mapping only from ringing onward.
- Configurable per DID/queue: sticky on/off, fallback queue, timeout override.
- Cron `ir_cron_scr_cleanup_expired` (cleanup of expired mappings, GDPR).
- Multi-company capable; security groups `group_scr_user` / `group_scr_manager`.
