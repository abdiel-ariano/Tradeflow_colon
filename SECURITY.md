# Security Policy

## Supported Versions

La rama `master` es la única soportada. Patches críticos se aplican
hacia atrás solo cuando hay deploy activo en producción.

## Reporting a Vulnerability

Por favor reporta vulnerabilidades vía email privado a:

**security@tradeflow.pa**

No abras un issue público en GitHub para reportar vulnerabilidades —
da tiempo al equipo de aplicar un parche antes de divulgación.

Incluí en tu reporte:

- Descripción del issue
- Pasos para reproducir (idealmente con un PoC)
- Versión y entorno donde se reproduce
- Impacto estimado (qué puede hacer un atacante)

Compromiso de respuesta:

- **48 horas hábiles** para acuse de recibo
- **14 días** para patch o mitigación documentada

Si reportás algo válido, te incluimos en el `SECURITY.md` salvo que
prefieras anonimato.

## Hardening baseline (OWASP Top 10 + GDPR)

Estado actual (julio 2026) — no reclamar “100% cobertura”; priorizar remediación continua:

| Área | Controles |
|------|-----------|
| A01 Access Control | Role decorators, seller tenancy, staff confirm for application review |
| A02 Crypto | Argon2 passwords; OTP / password-reset tokens hashed at rest (SHA-256) |
| A03 Injection | ORM default path; Analytics SQL SELECT-only guard; CSP JSON blocks |
| A04/A07 Auth | django-axes, email verification default on, OAuth not on bare GET |
| A05 Misconfig | CSP/HSTS/Secure cookies; public `/health/ready/` without config leak |
| A06 Components | CI Bandit + pip-audit (fail on HIGH) |
| A08 Integrity | Signed logistics webhooks; SSRF URL validation on save + dispatch |
| A09 Logging | Security event middleware; `purge_security_logs` retention job |
| A10 SSRF | Outbound URL validator; Analytics DB host allowlist in production |
| GDPR | Consent at signup, marketing opt-in, export + anonymize in My Profile |

Ops checks:

```bash
python manage.py release_check
python manage.py purge_security_logs --days 90
```

`EXPO_DEMO_MODE` remains supported for investor/Expo demos (`release_check` only warns).
Turn it off when an environment is production-only.

See also `SECURITY_AUDIT_2026-06.docx` for the earlier audit snapshot.
