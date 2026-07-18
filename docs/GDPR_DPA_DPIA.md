# GDPR — DPA & DPIA checklist (TradeFlow Colón)

This document is an **operational template**, not legal advice. Have counsel
review before signing with processors or expanding into the EEA/UK.

## 1. Processor inventory (update when vendors change)

| Processor | Purpose | Data categories | Transfer |
|-----------|---------|-----------------|----------|
| Supabase | Postgres + Storage | Accounts, orders, media | Cloud region per project |
| Resend | Transactional email | Email, name | US / Resend regions |
| Groq | Marketplace + Analytics AI chat | Free-text prompts, optional sales aggregates | US API |
| Railway (or host) | App hosting | Logs, env, sessions | Host region |
| OAuth IdPs (Google / Microsoft / LinkedIn) | Social login | Email, name, profile | Per IdP |
| Stripe (if enabled) | Payments | Billing metadata | Stripe regions |

## 2. Data Processing Agreement (DPA) checklist

For each processor above, confirm you have:

- [ ] Signed DPA / SCC (or equivalent) covering Art. 28 duties
- [ ] Documented subprocessors list
- [ ] Deletion / return of data on contract end
- [ ] Breach notification timelines aligned with your policy
- [ ] Region / transfer mechanism recorded

## 3. DPIA triggers (run before go-live in EEA or high-risk features)

Perform a Data Protection Impact Assessment when you:

- Persist precise **GPS** at checkout for many users
- Send free-text chat to an **LLM provider** (Groq)
- Process children’s data (TradeFlow should not)
- Introduce new advertising / third-party analytics cookies

### DPIA outline

1. **Description** of processing and assets
2. **Necessity & proportionality**
3. **Risks** to data subjects (confidentiality, discrimination, loss of control)
4. **Mitigations** already in product:
   - Location consent checkbox at checkout
   - Marketing opt-in; export + anonymize in My Profile
   - OTP/reset hashed at rest; staff TOTP optional
   - AI disclosure in chat UIs; `send_default_pii=False` in Sentry
5. **Residual risk** and residual owner sign-off

## 4. Retention jobs

```bash
python manage.py purge_security_logs --days 90
```

Schedule via cron/Railway. Adjust days with counsel for accounting holds.

## 5. Contact

Privacy requests: see in-app Privacy Policy contact email / `TRADEFLOW_CONTACT_EMAIL`.
