#nullable disable
using CallFlow;
using System;
using System.Net.Http;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using TCX.Configuration;
using TCX.PBXAPI;

// Smart Callback Routing – outbound reporting for 3CX V20 (Call Processing Script).
//
// === ALTERNATIVE / NOT THE RECOMMENDED WAY ===
// In production, outbound recording runs via the CRM template call journaling
// (3cxcrm -> POST /api/3cx/outbound), which does NOT interfere with the call.
// This script is only the alternative if no CRM template is used. It hooks into
// the dial-code trigger, which INTERCEPTS the call -> the script must dial the
// external number ITSELF (risk regarding the dial format, see VERIFY below).
//
// NOTE: NO HMAC signature (System.Security.Cryptography cannot be referenced).
// Therefore do NOT set a signing secret in Odoo – the X-API-Key is sufficient.
namespace dummy
{
    public class SmartCallbackOutbound : ScriptBase<SmartCallbackOutbound>
    {
        const string OdooBaseUrl   = "https://CHANGE-ME.odoo.example.com";
        const string ApiKey        = "CHANGE-ME";
        const int    HttpTimeoutMs = 1500;   // the report must not delay the call

        static readonly HttpClient Http = new HttpClient();

        public override async Task<bool> StartAsync()
        {
            if (MyCall.IsInbound || !(MyCall.Caller.DN is Extension ext))
                return false;

            var extension = ext.Number ?? "";              // calling extension
            var number    = MyCall.Caller.CalledNumber ?? ""; // dialed external number

            if (string.IsNullOrEmpty(extension) || string.IsNullOrEmpty(number))
                return false;

            // 1) Report to Odoo (fire-and-forget, swallow errors).
            try
            {
                var body = "{\"event\":\"ringing\",\"extension\":\"" + Esc(extension)
                         + "\",\"number\":\"" + Esc(number) + "\"}";

                using (var req = new HttpRequestMessage(
                    HttpMethod.Post, OdooBaseUrl.TrimEnd('/') + "/api/3cx/outbound"))
                {
                    req.Headers.TryAddWithoutValidation("X-API-Key", ApiKey);
                    req.Content = new StringContent(body, Encoding.UTF8, "application/json");
                    using (var cts = new CancellationTokenSource(HttpTimeoutMs))
                        await Http.SendAsync(req, cts.Token);
                }
                MyCall.Info($"SmartCallbackOutbound: reported {extension}->{number}");
            }
            catch (Exception ex2)
            {
                MyCall.Info($"SmartCallbackOutbound: report failed ({ex2.Message})");
            }

            // 2) Dial the external number (mandatory with the dial-code trigger!).
            // VERIFY: confirm the destination format for external dialing against your V20.
            if (DestinationStruct.TryParse(number + ".", out var dest))
            {
                var result = await MyCall.RouteToAsync(dest);
                MyCall.Info($"SmartCallbackOutbound: route {number} ({result})");
                return true;
            }

            return false;
        }

        static string Esc(string s) => (s ?? "").Replace("\\", "\\\\").Replace("\"", "\\\"");
    }
}
