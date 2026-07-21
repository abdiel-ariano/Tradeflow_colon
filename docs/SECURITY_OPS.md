# Security operations runbook (TradeFlow Colón)

Operational checklist for cybersecurity hardening already in the product.
This is **not** a substitute for legal counsel or vendor DPAs.

## 1. Production flags

| Setting | Production recommendation |
|---------|---------------------------|
| `DEBUG` | `false` |
| `EXPO_DEMO_MODE` | keep `false` outside investor demos (demo still supported) |
| `STAFF_MFA_REQUIRED` | `true` (auto-skipped only when `EXPO_DEMO_MODE=true`) |
| `ALLOW_MOCK_PLAN_PAYMENT` | `false` |
| `REQUIRE_EMAIL_VERIFICATION` | `true` |
| `SENTRY_DSN` | set to your project DSN |
| `SENTRY_TRACES_SAMPLE_RATE` | `0.05` (or lower) |

## 2. Scheduled jobs

```bash
# Daily SaaS subscription processing
python manage.py process_seller_subscriptions

# Weekly security-log retention (90 days default)
python manage.py purge_security_logs --days 90
```

Railway: create Cron Jobs with the schedules documented in `.env.example`.

## 3. Secrets hygiene

- Rotate `SECRET_KEY` if leaked; invalidate sessions after rotation.
- Staff TOTP secrets are wrapped with `SECRET_KEY`. After rotation, authenticator
  codes stop working — staff should sign in with a **backup code**, then re-enroll.
  Backup code hashes are SHA-256 and **do not** depend on `SECRET_KEY`.
- If backup codes are exhausted after a rotation:

  ```bash
  python manage.py reset_staff_mfa <username> --yes
  ```

  Then the user enrolls again at `/staff-mfa/setup/`.
- Store Resend / Groq / Supabase / Sentry keys only in the host secret store.
- Prefer short-lived tokens for OAuth apps; revoke unused IdP credentials.
- Never commit `.env`; keep `.env.example` as the non-secret template.

## 4. Breach notification (skeleton)

1. Contain: rotate secrets, revoke sessions, disable compromised users.
2. Preserve: export relevant `SecurityEvent` / app logs (do not purge yet).
3. Assess: data categories, volume, jurisdictions.
4. Notify: controllers / DPA / users per counsel timelines.
5. Remediate: patch, post-mortem, update this runbook.

Contact for privacy/security: `TRADEFLOW_CONTACT_EMAIL` / `security@tradeflow.pa` (see `SECURITY.md`).

Public disclosure file (Cloudflare Security Insights):

- `https://tradeflowcolon.com/.well-known/security.txt`
- Legacy alias: `/security.txt`
- Crawl policy companion: `/robots.txt` (blocks common AI scrapers)

## 5. Cloudflare Security Insights checklist

These toggles are **account/zone settings** (not Django). After deploy of
`security.txt` / `robots.txt`, clear remaining insights in the dashboard:

| Insight | Action in Cloudflare |
|---------|----------------------|
| Security.txt not configured | Should clear after `/.well-known/security.txt` is live; re-scan |
| Bot Fight Mode not enabled | Security → Bots → enable **Bot Fight Mode** (or Super Bot Fight) |
| Block AI bots | Security → Bots → enable **Block AI bots** |
| AI Labyrinth | Security → Bots → enable **AI Labyrinth** (honeypot for scrapers) |

Also confirm the zone proxies `tradeflowcolon.com` (orange cloud) so bot
features apply at the edge.

## 6. Related docs

- `SECURITY.md` — vulnerability reporting + OWASP/GDPR baseline
- `docs/GDPR_DPA_DPIA.md` — processor inventory + DPA/DPIA checklist
