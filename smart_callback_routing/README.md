# Smart Callback Routing (3CX + Odoo)

[![License: AGPL-3](https://img.shields.io/badge/licence-AGPL--3-blue.png)](http://www.gnu.org/licenses/agpl-3.0-standalone.html)

Sticky callback routing between **3CX V20** and **Odoo 19**: when an external
contact calls back, the call preferably rings the employee (3CX extension) who
last called that contact — temporary, TTL-based, non-blocking.

Verified on Odoo 19 **Community and Enterprise** (no Enterprise dependencies —
fresh-install + full test suite green on the official `odoo:19` CE image).

## Features

- **Temporary callback affinity** — when an employee dials out, Odoo stores a
  TTL-based mapping `phone number → extension` (default 2 h). No permanent CRM
  ownership.
- **"Last Outbound Wins"** — the latest qualifying outbound attempt overwrites
  the mapping (upsert; the first-contact timestamp is preserved).
- **Non-blocking by design** — the routing API answers `{"mode": "default"}` on
  any internal error (HTTP 200, never an empty 500); the 3CX side falls back to
  its normal routing on timeout, so no call is ever lost.
- **Kill switch** — a single settings toggle pauses sticky routing server-side
  without touching the phone system.
- **Best-effort presence** — optional presence feed lets the lookup skip
  busy/DND/offline extensions; unknown state counts as available.
- **GDPR-friendly** — expired mappings are deleted automatically by a cron job
  (every 30 minutes); routing-decision logging can be disabled.
- **Multi-company aware** — mappings, extensions and logs are scoped per company
  with record rules.
- Monitoring UI: active mappings and a routing-decision log (latency, decision,
  fallback reason) under the *Callback Routing* menu.

## How it works

```
Employee calls contact (outbound via 3CX)
        │  3CX CRM template call journaling → POST /api/3cx/outbound
        ▼
Odoo stores mapping: number → extension (TTL, e.g. 120 min)

Contact calls back (inbound)
        │  3CX call processing script → POST /api/3cx/callback-routing
        ▼
   ┌─ valid mapping & extension available → {"mode": "sticky_first", "extension": …}
   │       3CX rings that extension first; no-answer fallback = normal queue
   └─ otherwise / kill switch / error    → {"mode": "default"} → normal routing
```

- **Outbound recording** runs in production via the 3CX **CRM template call
  journaling** (shared template `docs/3cx_cfd/3cx_odoo_v20.xml`), which does not
  interfere with the call. A call-processing-script alternative is included.
- **Inbound lookup** is done by a small **call processing script**
  (`docs/3cx_cfd/SmartCallbackRouting.cs`) pasted directly into the 3CX admin
  console; a DID suffix filter limits it to your main number.
- A **cron job** cleans up expired mappings (TTL / GDPR).

## Requirements

- Odoo **19** (Community or Enterprise; depends on `base`, `base_setup`, `hr`)
- 3CX **V20 self-hosted** with **Call Processing Scripts** available
  (on 3CX-hosted PBX the script option may be disabled)

## Installation

1. Copy `smart_callback_routing` into your addons path.
2. Update the app list and install **Smart Callback Routing (3CX)**.
3. Open **Settings → Smart Callback Routing** and generate an API key.

## Configuration

**Odoo side** (Settings → Smart Callback Routing):

- **API key** (mandatory; without it every request is rejected with 401)
- Optional HMAC signing secret (not usable with the script sandbox — see docs)
- Sticky TTL (default 120 min), first-ring timeout (default 12 s),
  default country prefix (default 49)
- Skip rules for busy/offline/DND extensions (need a presence feed)
- **Pause sticky routing (kill switch)**
- Routing-decision logging on/off

**3CX side**: deploy the inbound call processing script and enable the CRM
template call journaling. Step-by-step instructions, the effectiveness matrix
(what is controlled by Odoo vs. by 3CX) and an example deployment walkthrough
are in [`docs/3cx_cfd/README.md`](docs/3cx_cfd/README.md),
[`docs/3cx_cfd/BUILD_GUIDE.md`](docs/3cx_cfd/BUILD_GUIDE.md) and
[`docs/CONFIG_GUIDE.md`](docs/CONFIG_GUIDE.md).

## API reference

All endpoints expect a JSON body (URL-encoded form fallback is supported) and
the header `X-API-Key: <key>`. If a signing secret is set, additionally
`X-Signature: <hex(hmac_sha256(body, secret))>`.

### `POST /api/3cx/outbound`

Report an outbound call (from ringing state onward).

```json
{ "event": "ringing", "extension": "105", "number": "+491701234567", "call_id": "abc-123" }
```

Response: `{"status": "ok", "phone": "+491701234567", "extension": "105", "expires_at": "..."}`

`event` must be one of `ringing|answered|busy|noanswer`, otherwise the event is
ignored (3CX `calltype` values like `Outbound`/`Notanswered` are mapped
automatically).

### `POST /api/3cx/presence` (optional)

```json
{ "extension": "105", "state": "available", "registered": true }
```

`state`: `available|busy|dnd|offline|unknown`.

### `POST /api/3cx/callback-routing`

Inbound lookup, called on an incoming call.

```json
{ "callerid": "+491701234567", "did": "089123456", "queue": "PROJECTS" }
```

Response on a hit:

```json
{ "mode": "sticky_first", "extension": "105", "timeout": 12, "fallback": "PROJECTS" }
```

Response without a hit: `{ "mode": "default" }`

> **Important (EC-005):** The 3CX script MUST have its own fallback in case
> Odoo is unreachable (HTTP timeout → default routing). The Odoo API is
> non-blocking, but cannot answer if Odoo is completely down.

## Security

- Only requests with a valid `X-API-Key` are answered (constant-time
  comparison; otherwise HTTP 401). Without a configured key the API is locked.
- Optional HMAC-SHA256 signature of the raw body (`X-Signature`).
- Recommendation: HTTPS via reverse proxy and an IP allowlist restricted to the
  3CX address.
- Phone numbers are stored only as normalized, TTL-bound mappings and deleted
  automatically by cron (GDPR).
- Two access groups: *User* (read-only monitoring) and *Manager*
  (configuration); multi-company record rules on all models.

## Changelog

See [CHANGELOG.md](CHANGELOG.md).

## License

[AGPL-3](LICENSE) — GNU Affero General Public License v3.0.
