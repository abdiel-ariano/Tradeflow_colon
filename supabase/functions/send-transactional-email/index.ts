// =============================================================================
// Supabase Edge Function: send-transactional-email
// =============================================================================
// Relays transactional email through Gmail SMTP from Supabase's network.
//
// WHY: hosting platforms such as Railway (Free/Trial/Hobby) block outbound SMTP
// (ports 25/465/587) with "Network is unreachable" (Errno 101). Supabase Edge
// Functions run on Deno Deploy, whose network DOES allow outbound SMTP, so the
// Django app calls this function over HTTPS (port 443, never blocked) and the
// function sends the email via the project's Gmail account.
//
// Django sends a POST with JSON: { to, subject, html, text, from, type, ... }
// (see core/email_service.py::_build_supabase_payload). The Authorization
// header carries the Supabase service_role key (a valid JWT), so the default
// gateway JWT verification accepts it — deploy WITHOUT --no-verify-jwt.
//
// Required Edge Function secrets (supabase secrets set ...):
//   GMAIL_USER            full Gmail address used to authenticate (e.g. you@gmail.com)
//   GMAIL_APP_PASSWORD    16-character Gmail App Password (NOT your login password,
//                         NOT a 6-digit 2FA code)
// Optional:
//   DEFAULT_FROM_NAME     display name for the From header (default "TradeFlow Colón")
// =============================================================================
import { SMTPClient } from "https://deno.land/x/denomailer@1.6.0/mod.ts";

const GMAIL_USER = (Deno.env.get("GMAIL_USER") ?? "").trim();
const GMAIL_APP_PASSWORD = (Deno.env.get("GMAIL_APP_PASSWORD") ?? "").trim();
const DEFAULT_FROM_NAME = (Deno.env.get("DEFAULT_FROM_NAME") ?? "TradeFlow Colón").trim();

const JSON_HEADERS = { "Content-Type": "application/json" };

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: JSON_HEADERS });
}

Deno.serve(async (req: Request): Promise<Response> => {
  if (req.method !== "POST") {
    return json({ error: "method_not_allowed" }, 405);
  }

  if (!GMAIL_USER || !GMAIL_APP_PASSWORD) {
    return json(
      { error: "gmail_not_configured", detail: "Set GMAIL_USER and GMAIL_APP_PASSWORD secrets." },
      500,
    );
  }

  let payload: Record<string, unknown>;
  try {
    payload = await req.json();
  } catch {
    return json({ error: "invalid_json" }, 400);
  }

  const to = String(payload.to ?? payload.recipient ?? "").trim();
  const subject = String(payload.subject ?? "").trim();
  const html = typeof payload.html === "string" ? payload.html : "";
  const text = typeof payload.text === "string" ? payload.text : "";

  if (!to) {
    return json({ error: "missing_recipient" }, 400);
  }

  // Gmail requires the From address to be the authenticated account (or a
  // verified alias). We always send as GMAIL_USER to avoid 5xx rejections,
  // keeping a friendly display name.
  const from = `${DEFAULT_FROM_NAME} <${GMAIL_USER}>`;
  const content = text && text.length > 0 ? text : "This email requires an HTML-capable client.";

  const client = new SMTPClient({
    connection: {
      hostname: "smtp.gmail.com",
      port: 465,
      tls: true,
      auth: { username: GMAIL_USER, password: GMAIL_APP_PASSWORD },
    },
  });

  try {
    await client.send({
      from,
      to,
      subject,
      content,
      html: html && html.length > 0 ? html : undefined,
    });
    await client.close();
    return json({ ok: true, channel: "gmail-smtp" }, 200);
  } catch (err) {
    try {
      await client.close();
    } catch (_) {
      // ignore close errors
    }
    return json({ error: "smtp_send_failed", detail: String(err).slice(0, 600) }, 502);
  }
});
