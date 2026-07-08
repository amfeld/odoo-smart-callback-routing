# 3CX V20 – Integration: Call Processing Scripts (recommended)

> **Recommended way (V20, no external tool):** **Call Processing Scripts** —
> C# code that you paste **directly into the 3CX admin console** and compile there
> (*Add call processing script → "Create Call Processing Script"*).
> The former route via the external Call Flow Designer (`.zip` build, "Upload call
> processing script project") is NOT required and only remains in the appendix.

## Two separate scripts (one script = one trigger)

- **Inbound (routing):** `SmartCallbackRouting.cs`, trigger **"When a call is
  received on a trunk"** (or "When this DID is called").
- **Outbound (recording):** runs in production via the **CRM template call
  journaling** (`3cxcrm` → `/api/3cx/outbound`), which **does not interfere with
  the call**. The bundled `SmartCallbackOutbound.cs` (dial-code trigger) is only
  the **alternative**.

> **Most common mistake:** putting the inbound script on the **dial-code trigger**
> → it never fires for incoming calls. There are exactly three triggers; for
> inbound only "…on a trunk" or "…this DID" counts. First diagnosis: the
> `MyCall.Info("…TRIGGER fired…")` line is already the very first line in
> `SmartCallbackRouting.StartAsync()` — if it does NOT appear in the 3CX script
> log during an external test call, it is a trigger/trunk issue, not code.

## Inbound script setup

1. Admin console → **Integrations → Call Scripts** (or *Advanced → Call Flow Apps →
   + Add → "Create Call Processing Script"*).
2. Choose a name (lowercase, no special characters). **"Run this script" =
   "When a call is received on a trunk"**, select the **trunk** on which the
   external calls come in.
3. Paste the content of **`SmartCallbackRouting.cs`**; adjust at the top:

   | Constant | Value |
   |---|---|
   | `OdooBaseUrl` | `https://<your-odoo-instance>` |
   | `ApiKey`      | API key from *Odoo → Settings → Smart Callback Routing* |
   | `HttpTimeoutMs` | 1200 (keep it short – the Odoo API is non-blocking) |

   Do **not** set a signing secret in Odoo — HMAC is not possible in the script
   sandbox; the `X-API-Key` is sufficient.
4. Save → wait for **"Compilation successful!"**.
5. Test: call from outside → the `TRIGGER fired` line must appear in the 3CX
   script log, and the decision in Odoo under *Callback Routing → Routing Log*.

## Behavior of the inbound script

```
[Incoming call on trunk]
   ├─ DID does not match OnlyDidSuffix (main number) → return false (default routing)
   └─ POST /api/3cx/callback-routing  {callerid, did}
        ├─ mode == "sticky_first" → RouteToAsync(Extension.<ext>.)  → return true
        └─ mode == "default" / error / timeout → return false (= 3CX default routing)
```

> **DID filter:** The trunk trigger fires for ALL incoming calls on the trunk.
> `OnlyDidSuffix` (at the top of the script, e.g. `"89123456"`) limits the
> interception to the main number — the queue keeps its DID, NO DID has to be
> re-pointed to the script. That is why you should use the trunk trigger, not
> the DID trigger: with the DID trigger the script owns the call completely
> (`return false` = hang up!), with the trunk trigger `return false` means
> "continue routing normally".

`RouteToAsync` returns as soon as the route has been handed over. The no-answer
fallback (rings too long / busy) is handled by the ring/forwarding timeout of the
extension or 3CX — not by this script. On `false` the normal 3CX routing applies;
this makes the whole thing non-blocking and never loses a call, even if Odoo is
offline.

## What the Odoo configuration does (and does not) affect in script mode

The call processing script does NOT enforce `timeout`/`fallback` from the API
response (`RouteToAsync` = handover only). These two tasks are handled by the
3CX extension. Therefore:

| Odoo config | Effective? | Where it happens instead |
|---|---|---|
| Settings → API key | ✅ | — (mandatory for all endpoints) |
| Settings → **"Pause sticky routing (kill switch)"** | ✅ | server-side kill switch: the API answers `default` without touching 3CX |
| Settings → TTL / default country prefix | ✅ | — (mapping lifetime, normalization) |
| Settings → first-ring timeout | ❌ (API response field only) | 3CX user → call forwarding → "No answer timeout" |
| Fallback queue | ❌ (API mirrors `queue`/`did` from the request) | 3CX user → "Unanswered calls" **and** "Busy or not registered" → system extension of the queue (voicemail checkbox off!) |
| Extensions (scr.extension) | (✅) | only relevant if presence is pushed; without a feed every extension counts as available |

> The former "DID/queue configuration" model was removed in 2.0: DID scoping is
> done by the `OnlyDidSuffix` filter in the inbound script, gating by the global
> kill switch. First-ring/fallback would only be effective in CFD variant B
> (transfer components).

## Outbound via CRM journaling (instead of a script)

The **shared 3CX CRM template** (copy here: [`3cx_odoo_v20.xml`](3cx_odoo_v20.xml),
identical in `3cxcrm/upload_on_3cx_pbx/`) contains a `ReportCall` scenario that
reports outgoing calls to `/api/3cx/outbound` (fields `number`=`[Number]`,
`extension`=`[Agent]`, `calltype`=`[CallType]`). To activate:

1. Upload the template `3cx_odoo_v20.xml` in 3CX (for updates: the version
   attribute is bumped; the safest way is **Remove → Add again**, then re-enter
   the values).
2. In the CRM integration, fill the parameter **"Smart Callback API Key"** with
   the key from *Odoo → Settings → Smart Callback Routing* (this is a
   **different** key than the lookup `ApiKey`).
3. **Enable call journaling** (checkbox "Enable Call Journaling").

Does not interfere with the call; reports at the end of the call — sufficient
for the sticky mapping.

**Who needs which template parameter?**

| Parameter | Belongs to | May stay empty if … |
|---|---|---|
| `ApiKey` + `Host odoo` | `3cxcrm` (contact lookup/caller display) | … only callback routing is wanted — the contact search then simply returns no matches. |
| `Smart Callback API Key` (`scrapikey`) + "Enable Call Journaling" | this module | … only the caller display is wanted — the `ReportCall` scenario then sends nothing (SkipIf). |

---

## Appendix: old way via Call Flow Designer (only if needed)

> The importable `.zip` for "Advanced → Call Flow Apps" is **compiler output** of
> the Call Flow Designer (Build → Build All) and CANNOT be created by hand. The
> building blocks `inbound_full_script.cs` / `inbound_signature_snippet.cs` are
> only needed in that case. For the recommended call processing script way they
> are **not** required.

Detailed CFD step-by-step guide: see [`BUILD_GUIDE.md`](BUILD_GUIDE.md).
