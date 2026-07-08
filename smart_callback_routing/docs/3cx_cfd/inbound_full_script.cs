// Variant B – complete inbound logic in a single script component.
// Calls /api/3cx/callback-routing and sets output variables on which the
// flow then branches with Condition/Transfer components.
//
// Output variables (create them in the CFD):
//   RouteMode      (string)  -> "sticky_first" | "default"
//   RouteExtension (string)  -> target extension for sticky_first
//   RouteTimeout   (int)     -> first-ring timeout in seconds
//   RouteFallback  (string)  -> fallback queue/ring group
//
// PRINCIPLE (EC-005): on ANY error/timeout -> RouteMode = "default".
// The flow then routes to the default routing. Never block.

using System;
using System.Net.Http;
using System.Text;
using System.Text.Json;
using System.Security.Cryptography;

const string OdooBaseUrl   = "https://CHANGE-ME.odoo.example.com";
const string ApiKey        = "CHANGE-ME";
const string SigningSecret = "";     // optional
const int    HttpTimeoutMs = 1200;   // keep short! the API is non-blocking

// --- Inputs from the call (adapt the CFD property access) ---
string callerId = (string)Project.Variables["CallerID"];
string did      = (string)Project.Variables["DID"];
string queue    = (string)Project.Variables["Queue"];

// Defaults = safe fallback
Project.Variables["RouteMode"]      = "default";
Project.Variables["RouteExtension"] = "";
Project.Variables["RouteTimeout"]   = 12;
Project.Variables["RouteFallback"]  = queue ?? "";

try
{
    string body = JsonSerializer.Serialize(new {
        callerid = callerId, did = did, queue = queue
    });

    using (var client = new HttpClient())
    {
        client.Timeout = TimeSpan.FromMilliseconds(HttpTimeoutMs);

        var req = new HttpRequestMessage(HttpMethod.Post,
            OdooBaseUrl.TrimEnd('/') + "/api/3cx/callback-routing");
        req.Headers.Add("X-API-Key", ApiKey);
        if (!string.IsNullOrEmpty(SigningSecret))
            req.Headers.Add("X-Signature", HmacHex(body, SigningSecret));
        req.Content = new StringContent(body, Encoding.UTF8, "application/json");

        var resp = client.SendAsync(req).GetAwaiter().GetResult();
        if (resp.IsSuccessStatusCode)
        {
            string json = resp.Content.ReadAsStringAsync().GetAwaiter().GetResult();
            using (var doc = JsonDocument.Parse(json))
            {
                var root = doc.RootElement;
                string mode = GetStr(root, "mode") ?? "default";
                if (mode == "sticky_first")
                {
                    Project.Variables["RouteMode"]      = "sticky_first";
                    Project.Variables["RouteExtension"] = GetStr(root, "extension") ?? "";
                    if (root.TryGetProperty("timeout", out var t) && t.TryGetInt32(out int to))
                        Project.Variables["RouteTimeout"] = to;
                    string fb = GetStr(root, "fallback");
                    if (!string.IsNullOrEmpty(fb)) Project.Variables["RouteFallback"] = fb;
                }
            }
        }
    }
}
catch (Exception)
{
    // deliberately swallowed -> RouteMode stays "default"
}

// --- Helpers ---
static string GetStr(JsonElement e, string name)
    => e.TryGetProperty(name, out var v) && v.ValueKind == JsonValueKind.String
        ? v.GetString() : null;

static string HmacHex(string data, string secret)
{
    using (var h = new HMACSHA256(Encoding.UTF8.GetBytes(secret)))
    {
        byte[] hash = h.ComputeHash(Encoding.UTF8.GetBytes(data));
        var sb = new StringBuilder(hash.Length * 2);
        foreach (byte b in hash) sb.Append(b.ToString("x2"));
        return sb.ToString();
    }
}
