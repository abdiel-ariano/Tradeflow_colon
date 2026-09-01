# ⚠️ Documento deprecado — correo enterprise

**Este archivo ya no describe el comportamiento del código.**

Desde 2026 la aplicación envía correo transaccional exclusivamente vía **Resend**
(`core/email_service.py`). No se usa `SUPABASE_EMAIL_ENABLED` ni Gmail SMTP en
producción.

**Guía actual:** [CORREO_TRANSACCIONAL.md](CORREO_TRANSACCIONAL.md)

---

# TradeFlow Colón — correo transaccional en producción (histórico)

La aplicación **no usa Resend**. El envío es:
