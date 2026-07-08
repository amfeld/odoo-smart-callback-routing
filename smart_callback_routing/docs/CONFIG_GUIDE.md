# Configuration Guide – Smart Callback Routing (example deployment walkthrough)

> A concrete end-to-end setup example for a typical use case. All numbers,
> queue IDs and names are examples — replace them with your own values.
> General module/3CX docs: [README.md](../README.md), [3cx_cfd/BUILD_GUIDE.md](3cx_cfd/BUILD_GUIDE.md).

## Example scenario

MyCompany's main number **+49 89 123450-0** runs in 3CX into the queue
**800 "Front Desk"** and rings **all 4 front-desk agents** simultaneously
("ring all", 20 s).

Desired callback behavior:

> If **a project manager** was the last one to call the customer, the callback
> should **first ring that project manager**. If they do not answer (or there
> was no prior contact), the **front desk (queue 800)** rings as usual.

```
Project manager calls customer  ──▶  Odoo remembers: customer no. → PM extension (TTL 120 min)

Customer calls +49891234500 back
        │
        ▼
   3CX script queries Odoo  (POST /api/3cx/callback-routing)
        │
        ├── sticky_first → first the PM extension (12 s)
        │                     └─ not answered ──▶ queue 800 (4 front-desk agents)
        │
        └── default      → straight to queue 800 (4 front-desk agents)   ← all other callers
```

---

## Part A – Configuration in Odoo

### A.1 Global settings
**Settings → Smart Callback Routing**

| Field | Example value | Meaning |
|---|---|---|
| **API key** | button "Generate new key" | **Mandatory.** Without a key → every request 401. Note it down for 3CX. |
| HMAC signing secret | *(leave empty)* | Only if an additional signature check is wanted. |
| **Sticky TTL (minutes)** | `120` | How long the customer→PM mapping is valid (2 h). |
| **First-ring timeout (seconds)** | `12` | How long the PM rings alone before the queue takes over. |
| **Default country prefix** | `49` | So national numbers are normalized correctly. |
| Skip busy extension | on | Only effective with a presence feed, otherwise irrelevant. |
| Skip offline/unregistered | on | ditto |
| Skip DND extension | on | ditto |
| Log routing decisions | on | For monitoring/testing. |

### A.2 Kill switch (instead of DID/queue configuration)
The former "DID/queue configuration" model was **removed in 2.0** — which DID
the routing applies to is filtered by the inbound script itself
(`OnlyDidSuffix`), and timeout/fallback are handled by the 3CX forwarding rules
of the extensions (see part B).

Instead, **Settings → Smart Callback Routing** offers the switch
**"Pause sticky routing (kill switch)"**: while active, the routing API always
answers "default" — 3CX routes normally everywhere, without any change to the
phone system. Outbound mappings are still recorded.

### A.3 Extensions (optional)
**Callback Routing → Configuration → Extensions**

- **Not required for the basic function** — the project manager's extension is
  automatically part of the mapping created on outbound.
- Creating them is only worthwhile if you want (a) the employee mapping to be
  readable in the log or (b) busy/DND/offline extensions to be skipped
  (requires a presence feed).

---

## Part B – Configuration in 3CX

### B.1 Inbound (mandatory) – put the script in front of the queue
Smart routing must sit **in front of** queue 800, not behind it.

1. Deploy the call script **`SmartCallbackRouting.cs`**
   (Admin → Integrations → Call Scripts; details: [BUILD_GUIDE.md](3cx_cfd/BUILD_GUIDE.md) section 1).
2. Set at the top of the script:
   - `OdooBaseUrl` = `https://<your-odoo-url>`
   - `ApiKey` = the key from A.1
   - `SigningSecret` = empty
   - `HttpTimeoutMs` = `1200`
3. Point the **inbound rule** of the DID **+49891234500** to this script
   (instead of directly to queue 800 as before).
4. Make sure the **fallback/timeout exit** of the script goes to **queue 800** —
   so every call reaches the front desk when the PM does not answer OR Odoo does
   not respond (mandatory, EC-005).

Request sent by the script:
```json
{ "callerid": "<CallerID>", "did": "+49891234500", "queue": "800" }
```
Odoo response on a hit:
```json
{ "mode": "sticky_first", "extension": "<PM extension>", "timeout": 12, "fallback": "800" }
```

### B.2 Outbound (mandatory) – otherwise no mapping is ever created
Every outgoing call by a project manager must be reported to Odoo **from the
"ringing" state onward** (fire-and-forget, via 3CX Call Control API / webhook —
see BUILD_GUIDE section 2):
```json
POST /api/3cx/outbound
{ "event": "ringing", "extension": "<PM extension>", "number": "<customer number>", "call_id": "<id>" }
```
> ⚠️ Prerequisite: The project managers make calls through 3CX (desk phone/
> softphone/3CX app). If they call from a private mobile phone bypassing 3CX,
> there is no mapping and the callback always lands at `default` (queue 800).

### B.3 Presence (optional)
Only if busy/DND/offline should be skipped: report `POST /api/3cx/presence` on
every status change of an extension. Without this feed every extension counts
as available — the ring timeout catches the unreachable case anyway.

---

## Part C – Test (in order)

1. **Outbound:** PM calls an external test number → in Odoo under *Callback
   Routing → Active Mappings* the entry `test number → PM extension` appears.
2. **Inbound hit:** the same number calls +49891234500 → only the PM rings
   first (12 s).
3. **Fallback:** PM does not answer → the call lands in queue 800 (4 front-desk agents).
4. **Default:** an unknown number calls → straight to queue 800.
5. **Emergency:** briefly block Odoo → the call lands directly in queue 800 via
   the timeout.
6. All decisions traceable under *Callback Routing → Routing Log*.

---

## Open points (clarify before go-live)

- [ ] Which identifier does your script send as `did`/`queue`?
- [ ] Which mechanism reports outbound events (Call Control API vs. dialer vs. CRM journaling)?
- [ ] Document the project managers' extension numbers (for testing/monitoring).
- [ ] Is Odoo reachable via HTTPS from the 3CX network? Set an IP allowlist to the 3CX address.
