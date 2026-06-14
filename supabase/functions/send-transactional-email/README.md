# send-transactional-email (Supabase Edge Function)

Relays TradeFlow transactional email through **Gmail SMTP** from Supabase's
network. The Django app calls this function over HTTPS (port 443), so it works
even on hosts that block outbound SMTP (Railway Free/Trial/Hobby → `Errno 101
Network is unreachable`).

```
Django (Railway, HTTPS 443)  ──►  Supabase Edge Function  ──►  Gmail SMTP (465)
```

---

## Option A (recommended): deploy from GitHub — no local CLI

A GitHub Action (`.github/workflows/deploy-supabase-functions.yml`) deploys this
function automatically when changes under `supabase/functions/**` land on
`master` (i.e. when this PR is merged), and can also be run on demand from the
**Actions** tab → *Deploy Supabase Edge Functions* → *Run workflow*.

Add these **repository secrets** (GitHub → Settings → Secrets and variables →
Actions → New repository secret):

| Secret | Where to get it |
|--------|-----------------|
| `SUPABASE_ACCESS_TOKEN` | https://supabase.com/dashboard/account/tokens |
| `SUPABASE_PROJECT_REF` | Supabase Dashboard → Project Settings → General → *Reference ID* |
| `GMAIL_USER` *(optional)* | your Gmail address (e.g. `you@gmail.com`) |
| `GMAIL_APP_PASSWORD` *(optional)* | 16-char Gmail App Password |
| `DEFAULT_FROM_NAME` *(optional)* | display name, default "TradeFlow Colón" |

- If you add `GMAIL_USER` + `GMAIL_APP_PASSWORD` as repo secrets, the workflow
  also pushes them to the function on each deploy.
- If you prefer not to store the Gmail secrets in GitHub, set them once in the
  Supabase Dashboard (Edge Functions → Secrets) and omit those two repo secrets;
  the workflow will just deploy the code.

Then finish with **step 3** below (the Railway variables).

---

## Option B: deploy manually with the Supabase CLI

## 1. Set the function secrets

Use a Gmail **App Password** (16 chars, no spaces) — not your login password and
not a 6-digit 2FA code. Create it at https://myaccount.google.com/apppasswords
(requires 2-Step Verification enabled).

With the Supabase CLI (from the repo root):

```bash
supabase login
supabase link --project-ref <YOUR_PROJECT_REF>
supabase secrets set GMAIL_USER="youraccount@gmail.com"
supabase secrets set GMAIL_APP_PASSWORD="abcdabcdabcdabcd"
# optional
supabase secrets set DEFAULT_FROM_NAME="TradeFlow Colón"
```

(You can also set these in the Supabase Dashboard → Edge Functions → Secrets.)

## 2. Deploy the function

```bash
supabase functions deploy send-transactional-email
```

Deploy with the **default JWT verification** (do NOT pass `--no-verify-jwt`):
Django authenticates with the project `service_role` key, which is a valid JWT.

## 3. Configure the Django app (Railway variables)

```
SUPABASE_URL=https://<YOUR_PROJECT_REF>.supabase.co
SUPABASE_SERVICE_KEY=<service_role key>
SUPABASE_EMAIL_ENABLED=true
# optional (only if you renamed the function)
SUPABASE_EMAIL_FUNCTION=send-transactional-email
```

Redeploy the Railway service after changing variables.

## 4. Test

```bash
curl -i -X POST \
  "https://<YOUR_PROJECT_REF>.supabase.co/functions/v1/send-transactional-email" \
  -H "Authorization: Bearer <service_role key>" \
  -H "apikey: <service_role key>" \
  -H "Content-Type: application/json" \
  -d '{"to":"you@example.com","subject":"TradeFlow test","html":"<p>It works ✅</p>","text":"It works"}'
```

Expected: `{"ok":true,"channel":"gmail-smtp"}`. Then trigger a real flow (approve
an access request / place an order) and check the Edge Function logs in the
Supabase Dashboard.

## Notes

- The function always sends `From: "<DEFAULT_FROM_NAME>" <GMAIL_USER>` because
  Gmail only allows sending as the authenticated account (or a verified alias).
- If you get an auth error from Gmail (`535`), the App Password is wrong or
  2-Step Verification isn't enabled on the account.
