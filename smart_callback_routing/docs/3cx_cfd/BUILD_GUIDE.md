# 3CX V20 – Build Guide: Smart Callback Routing

This guide describes how to build the two call flows in 3CX V20 to work with
the Odoo module *Smart Callback Routing*.

**The idea in one sentence:** When an employee calls a contact (outbound), Odoo
remembers `number → extension` for a limited time. When the contact calls back
(inbound), 3CX first rings exactly this extension; if unreachable, the normal
queue routing applies.

---

## 0. What is needed up front (from the Odoo side)

| Item | Example | Source |
|---|---|---|
| Odoo base URL (HTTPS!) | `https://erp.example.com` | IT / Odoo admin |
| API key | `scr_live_xxx…` | Odoo → Settings → Smart Callback Routing |
| Signing secret (optional) | `s3cr3t…` | same place (only if enabled) |
| DID/queue names | `089123456`, `PROJECTS` | as maintained on the 3CX side |

Three HTTP endpoints are available (all `POST`, JSON body, header `X-API-Key`):

| Endpoint | Purpose |
|---|---|
| `POST /api/3cx/callback-routing` | **Inbound** lookup: "who should ring first?" |
| `POST /api/3cx/outbound` | **Outbound** report: create mapping |
| `POST /api/3cx/presence` | optional: push availability of an extension |

> **Response behavior (important):** The inbound API never blocks. If it finds
> no mapping or an error occurs, it answers with `{"mode":"default"}`.
> If Odoo is completely down, there is no response at all → then **3CX itself**
> must fall back to the default routing (see error/timeout exit below).

---

## 1. Flow "Inbound"

This is the actual routing flow. In 3CX **V20** there are two ways —
**variant A is recommended** because it works without Visual Studio:

| | Variant A – **Call Processing Script** | Variant B – visual CFD |
|---|---|---|
| What | paste a ready-made C# script directly | click the flow together in the Call Flow Designer |
| Deployment | Admin → **Integrations → Call Scripts** (or **Advanced → Call Flow Apps → + Add an App → Call Processing Script**) → paste the C# code into the *"Enter your C# code below"* field | Visual Studio → build → upload ZIP |
| File | **`SmartCallbackRouting.cs`** (in this folder, ready) | see section 1.4 |
| Prerequisite | script inherits from `CallFlow.ScriptBase<T>` ✓ | CFD desktop tool |

> **Note:** On 3CX-**hosted** PBX the script/call-control option may currently
> be disabled (per 3CX docs). On self-hosted V20 it is available.

### Variant A – Call Processing Script (recommended)

1. Admin console → **Integrations → Call Scripts** → *+ Add* (or
   **Advanced → Call Flow Apps → + Add an App → Call Processing Script**).
2. Copy the content of **`SmartCallbackRouting.cs`** into the *"Enter your C#
   code below"* field.
3. Adjust at the top of the script: `OdooBaseUrl`, `ApiKey`, possibly `SigningSecret`.
4. Save → assign an extension/DID to the app.
5. Point the **inbound rule** of the DID to this call script.

The script implements the complete flow diagram below: lookup, sticky attempt
of the extension, fallback queue and — on every error/timeout — return `false`
(= 3CX default routing applies). Three spots are marked with `VERIFY` and need
to be checked against your 3CX version (see section 1.5).

### 1.1 API response

Odoo answers the inbound lookup with one of two modes:

```json
// hit:
{ "mode": "sticky_first", "extension": "105", "timeout": 12, "fallback": "PROJECTS" }

// no hit / anonymous / sticky disabled:
{ "mode": "default" }
```

- `extension` – extension that should ring first
- `timeout`   – how many **seconds** it may ring before forwarding
- `fallback`  – queue/ring group for the no-answer case (may be missing → use default)

### 1.2 Flow diagram

```
 [Start / Incoming Call]
        │
        ▼
 [HTTP Request → /api/3cx/callback-routing]
        │   Body: {"callerid": <CallerID>, "did": <DID>, "queue": <Queue>}
        │
        ├──► error OR timeout (>1.5 s)  ────────────────┐
        │                                               │
        ▼                                               │
 [Condition:  mode == "sticky_first" ?]                 │
        │                                               │
        ├── no (mode == "default") ─────────────────────┤
        │                                               │
        └── yes                                         │
              ▼                                         │
        [Transfer → <extension>]                        │
        ring timeout = <timeout> seconds                │
              │                                         │
              ├── answered ─► (end)                     │
              │                                         │
              └── no answer / busy / DND / reject       │
                       ▼                                │
                [Transfer → <fallback>]                 │
                                                        ▼
                                          [Transfer → default queue/ring group]
                                          (own fallback if Odoo does not answer)
```

### 1.4 Variant B – visual CFD, components step by step

> Only needed if you use the visual designer instead of the call script (variant A).

**Create the project**
1. Call Flow Designer V20 → **File → New Project** → name `SmartCallbackRouting`.
2. `Main.flow` is created automatically (exactly one call flow per project).

**Component 1 – (optional) prepare body + signature**
- Only needed if a signing secret is used.
- Insert a **Script** component, code from `inbound_signature_snippet.cs`.
- Builds the JSON body and sets the variable `Signature` (for the `X-Signature` header).
- Without a secret: skip and build the body directly in the HTTP component.

**Component 2 – "Make HTTP Request"**
| Field | Value |
|---|---|
| Method | `POST` |
| URL | `https://<odoo>/api/3cx/callback-routing` |
| Header | `X-API-Key: <API key>` |
| Header | `Content-Type: application/json` |
| Header (opt.) | `X-Signature: <Signature>` |
| Body | `{"callerid":"<CallerID>","did":"<DID>","queue":"<Queue>"}` |
| **Timeout** | **1200 ms** (keep it short!) |
| Error/timeout exit | → **component 6** (default queue) |

> Insert `<CallerID>`, `<DID>`, `<Queue>` from the call properties of the
> incoming call. Parse the response into variables: `RouteMode`,
> `RouteExtension`, `RouteTimeout`, `RouteFallback`. (Alternatively do
> everything via script: `inbound_full_script.cs`.)

**Component 3 – "Condition"**
- Condition: `RouteMode == "sticky_first"`
- **true** → component 4
- **false** → component 6 (default routing)

**Component 4 – "Transfer" (sticky attempt)**
| Field | Value |
|---|---|
| Target | `RouteExtension` |
| Ring/no-answer timeout | `RouteTimeout` (seconds) |
| On no answer/busy/reject | → component 5 |

**Component 5 – "Transfer" (fallback queue)**
| Field | Value |
|---|---|
| Target | `RouteFallback` (if empty → default queue) |

**Component 6 – "Transfer" (default routing / emergency fallback)**
- Target: the normal queue/ring group that would be active without this module.
- Reached on `mode=default`, HTTP error or HTTP timeout.
- **This exit is mandatory** – it guarantees that no call is lost, even if Odoo
  is offline.

**Build & deploy**
1. **Build → Build All (Ctrl+B)** → assign an extension the first time → creates `SmartCallbackRouting.zip`.
2. 3CX console → **Advanced → Call Flow Apps** → upload the ZIP.
3. Point the **inbound rule** of the DID to this call flow app.

### 1.5 To verify against your 3CX version (`VERIFY` in the script)

The script follows exactly the API pattern of your existing
`InterceptInboundCall` (`ScriptBase<T>`, `MyCall.Caller.CallerID`,
`MyCall.Caller.CalledNumber`, `DestinationStruct.TryParse`,
`MyCall.RouteToAsync`, `MyCall.Info`). Three points depend on detail behavior
that could not be derived from that example:

1. **`RouteResult.Connected`** – check existence/name of the enum value. If it
   is named differently, adjust the condition "extension did NOT answer →
   fallback" accordingly (or leave the fallback to the extension's forwarding
   rules).
2. **Queue destination format `"Queue.<value>."`** – analogous to
   `"Extension.114."`. In 3CX, queues have an **extension number**; therefore
   prefer configuring the **3CX queue number** as fallback, not a name.
3. **First-ring `timeout`** – the Odoo `timeout` (seconds) is NOT enforced per
   call in the script; the extension's no-answer timeout applies. If that is
   not enough, set the timeout on the extension or extend the script with a
   time-based forwarding.

Whether `HttpClient` is allowed in the script sandbox should be checked briefly
against a test log on first deployment (`MyCall.Info`). Your example uses
`System.IO`/`Regex` – networking should be available, but it is the only point
not proven by the example.

---

## 2. Flow "Outbound" (report the mapping)

For inbound to have anything to route, every outgoing call must be reported to
Odoo **from the "ringing" state onward**. This is fire-and-forget – the
response does not matter, the call must not be delayed by it.

### 2.1 What to report with?

Outbound typically does **not** run via the CFD but via one of the following
3CX mechanisms (depending on the setup – the PBX admin chooses):

- **3CX Call Control API / webhook** on the call-state change to `ringing`, **or**
- a small custom outbound CFD/dialer that issues the HTTP call before the
  connection is established.

### 2.2 Request

```
POST https://<odoo>/api/3cx/outbound
Header: X-API-Key: <API key>
        Content-Type: application/json
        X-Signature: <hex(hmac_sha256(body, secret))>   # only if a secret is set
Body:
{
  "event": "ringing",
  "extension": "<calling extension>",
  "number":    "<dialed external number>",
  "call_id":   "<unique call ID>"
}
```

### 2.3 Rules (important!)

- `event` must be one of **`ringing` | `answered` | `busy` | `noanswer`**.
- **Do NOT report `failed`/`instant` attempts** – they should deliberately not
  create a mapping (otherwise every typo/instant hang-up would create a sticky
  rule).
- **One** report per outbound call is enough (e.g. on the transition to "ringing").
- Anonymous/invalid numbers are ignored server-side – no special case needed.

### 2.4 Flow diagram

```
 [Outbound call reaches state "ringing"]
        │
        ▼
 [HTTP Request → /api/3cx/outbound]   (timeout uncritical, ignore the response)
        │
        ▼
 [Call continues normally]
```

---

## 3. Optional: presence

If the availability check (prevents sticky routing to offline/DND extensions)
is to be used, report on every status change of an extension:

```
POST https://<odoo>/api/3cx/presence
Header: X-API-Key: <API key>
Body:   { "extension": "105", "state": "available", "registered": true }
```

`state`: `available | busy | dnd | offline | unknown`.
Without this feed every extension counts as available – the ring timeout in the
inbound flow catches the unreachable case anyway.

---

## 4. Test checklist

1. **Outbound:** employee (e.g. ext. 105) calls an external test number → in
   Odoo under *Callback Routing → Active Mappings* the entry `number → 105`
   appears.
2. **Inbound hit:** the same external number calls back → only ext. 105 rings
   first (for `timeout` seconds).
3. **Fallback:** do not answer on ext. 105 → the call lands in the `fallback`
   queue.
4. **Default:** an unknown number calls → straight to default routing
   (`mode=default`).
5. **Emergency:** briefly block the Odoo URL → the call lands in the default
   routing via the HTTP timeout (no lost call).
6. All decisions are visible in Odoo under *Callback Routing → Routing Log*.

---

## 5. Appendix: bundled files

| File | Content |
|---|---|
| `inbound_full_script.cs` | complete inbound logic as one C# script component (variant B) |
| `inbound_signature_snippet.cs` | HMAC signature only, rest via native HTTP component (variant A) |
| `outbound_example.http` | copy-paste example requests for all endpoints |

> Note for the PBX admin: The exact CFD variable names (call properties such as
> CallerID/DID) and whether `HttpClient` is allowed in the script depend on the
> concrete CFD version and must be adjusted while building. The HTTP endpoints,
> JSON fields and the `default`/timeout behavior, however, are fixed as above.
