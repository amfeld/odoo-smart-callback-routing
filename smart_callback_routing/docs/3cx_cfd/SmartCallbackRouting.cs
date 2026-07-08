#nullable disable
using CallFlow;
using System;
using System.Net.Http;
using System.Text;
using System.Text.RegularExpressions;
using System.Threading;
using System.Threading.Tasks;
using TCX.Configuration;
using TCX.PBXAPI;

// Smart Callback Routing – inbound interception for 3CX V20 (Call Processing Script).
// Trigger: "When a call is received on a trunk" (recommended) OR
//          "When this DID is called".  NOT "When a user dials a dial code" –
//          that one only fires for outbound/internal calls, never for inbound.
// IMPORTANT: outbound and inbound are TWO separate scripts (one script = one trigger).
// On incoming external calls it queries the Odoo API; on a sticky hit it routes
// to the extension that called last, otherwise/on error -> false (= 3CX default routing).
//
// NOTE on crypto: System.Security.Cryptography cannot be referenced in the script
//   sandbox. -> no HMAC signature; do NOT set a signing secret in Odoo
//   (the X-API-Key is sufficient).
// NOTE on fallback: RouteToAsync hands over the call and returns immediately
//   (= "handover ok", NOT "answered"). The no-answer behavior is therefore handled
//   by the extension/3CX, not by this script. If needed, configure a no-answer
//   forwarding rule on the extension pointing to the fallback queue.
namespace dummy
{
    public class SmartCallbackRouting : ScriptBase<SmartCallbackRouting>
    {
        const string OdooBaseUrl   = "https://CHANGE-ME.odoo.example.com";
        const string ApiKey        = "CHANGE-ME";
        const int    HttpTimeoutMs = 1200;   // keep short – the Odoo API is non-blocking

        // Only intercept calls to this DID (suffix comparison: covers "+49...",
        // "0049...", "0..."). All other DIDs on the trunk pass untouched into
        // the default routing. Empty ("") = script is active for all DIDs.
        // Example value – replace with the DID suffix of your main number
        // (matches the walkthrough number +49891234500 in docs/CONFIG_GUIDE.md).
        const string OnlyDidSuffix = "891234500";

        static readonly HttpClient Http = new HttpClient();

        public override async Task<bool> StartAsync()
        {
            var callerId = MyCall.Caller?.CallerID ?? "";
            var did      = MyCall.Caller?.CalledNumber ?? "";

            // Diagnostics: proves in the 3CX script log that the trigger fires at all.
            // If this line does NOT appear for an external test call, the problem is
            // the trigger/trunk (see header), not the code.
            MyCall.Info($"SmartCallbackRouting: TRIGGER fired (IsInbound={MyCall.IsInbound}, "
                      + $"caller='{callerId}', did='{did}', callerDN={MyCall.Caller?.DN?.GetType().Name})");

            // The trunk trigger already guarantees an incoming external call; the
            // strict `is ExternalLine` cast is deliberately omitted (it silently
            // bailed out in some V20 builds). It suffices: inbound + number present.
            if (!MyCall.IsInbound || string.IsNullOrEmpty(callerId))
                return false;

            // DID filter: with the trunk trigger the script fires for ALL incoming
            // calls on the trunk. Only the main number should be sticky-routed;
            // for all other DIDs return false immediately = normal 3CX routing
            // (the queue keeps its DID, nothing is "taken away").
            if (!string.IsNullOrEmpty(OnlyDidSuffix) && !did.EndsWith(OnlyDidSuffix))
            {
                MyCall.Info($"SmartCallbackRouting: DID '{did}' not the main number -> default routing");
                return false;
            }

            string mode = "default", extension = null;

            try
            {
                var body = "{\"callerid\":\"" + Esc(callerId) + "\",\"did\":\"" + Esc(did) + "\"}";

                using (var req = new HttpRequestMessage(
                    HttpMethod.Post, OdooBaseUrl.TrimEnd('/') + "/api/3cx/callback-routing"))
                {
                    req.Headers.TryAddWithoutValidation("X-API-Key", ApiKey);
                    req.Content = new StringContent(body, Encoding.UTF8, "application/json");

                    using (var cts = new CancellationTokenSource(HttpTimeoutMs))
                    {
                        var resp = await Http.SendAsync(req, cts.Token);
                        var json = await resp.Content.ReadAsStringAsync();

                        mode      = JsonVal(json, "mode") ?? "default";
                        extension = JsonVal(json, "extension");
                    }
                }
            }
            catch (Exception ex)
            {
                MyCall.Info($"SmartCallbackRouting: Odoo lookup failed ({ex.Message}) -> default");
                return false;
            }

            if (mode != "sticky_first" || string.IsNullOrEmpty(extension))
                return false;

            if (!DestinationStruct.TryParse("Extension." + extension + ".", out var extDest))
                return false;

            var result = await MyCall.RouteToAsync(extDest);
            MyCall.Info($"SmartCallbackRouting: {callerId}->{did} sticky to {extension} ({result})");
            return true;
        }

        // Minimal, dependency-free JSON value extractor (string OR number).
        static string JsonVal(string json, string key)
        {
            var m = Regex.Match(json ?? "",
                "\"" + Regex.Escape(key) + "\"\\s*:\\s*\"?([^\",}]+)\"?");
            return m.Success ? m.Groups[1].Value.Trim() : null;
        }

        static string Esc(string s) => (s ?? "").Replace("\\", "\\\\").Replace("\"", "\\\"");
    }
}
