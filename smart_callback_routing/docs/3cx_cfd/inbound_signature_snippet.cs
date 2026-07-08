// Variant A – script component ONLY for the HMAC signature.
// The actual HTTP call is made afterwards by the native "Make HTTP Request" component.
//
// Prerequisite in the CFD: a variable "JsonBody" (string) already contains the
// finished request body, e.g. assembled from the call properties:
//   {"callerid":"<CallerID>","did":"<DID>","queue":"<Queue>"}
//
// This component sets the variable "Signature" (string), which you pass in the
// HTTP component as header  X-Signature: <Signature>.
// If no signing secret is set, you can omit this component.

using System;
using System.Security.Cryptography;
using System.Text;

const string SigningSecret = "";   // <-- HMAC secret from Odoo, otherwise leave empty

string body = (string)Project.Variables["JsonBody"]; // adapt the CFD variable access

string signature = "";
if (!string.IsNullOrEmpty(SigningSecret))
{
    using (var hmac = new HMACSHA256(Encoding.UTF8.GetBytes(SigningSecret)))
    {
        byte[] hash = hmac.ComputeHash(Encoding.UTF8.GetBytes(body));
        var sb = new StringBuilder(hash.Length * 2);
        foreach (byte b in hash) sb.Append(b.ToString("x2")); // hex(hmac_sha256(body))
        signature = sb.ToString();
    }
}

Project.Variables["Signature"] = signature; // adapt the CFD variable access
