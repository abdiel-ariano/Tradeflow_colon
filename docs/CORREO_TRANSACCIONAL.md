# Correo transaccional — TradeFlow Colón

## Canal oficial: Resend

En **producción y staging** todos los correos transaccionales salen por la API
HTTP de [Resend](https://resend.com), implementada en `core/email_service.py`.

| Variable | Descripción |
|----------|-------------|
| `RESEND_API_KEY` | Clave desde [resend.com/api-keys](https://resend.com/api-keys) |
| `RESEND_FROM_EMAIL` | Remitente con dominio verificado en Resend |
| `DEFAULT_FROM_EMAIL` | Fallback si `RESEND_FROM_EMAIL` está vacío |
| `PUBLIC_BASE_URL` | Base para enlaces en HTML (reset, verificación) |
| `TRADEFLOW_CONTACT_EMAIL` | Contacto visible en plantillas |
| `REQUIRE_EMAIL_VERIFICATION` | `true` exige OTP al registrarse |

---

## Flujos que envían correo

| Flujo | Módulo / comando |
|-------|------------------|
| OTP verificación registro | `core/email_service.py` → `send_verification_email` |
| Reset contraseña | Django auth + plantillas en `templates/registration/` |
| Ciclo de vida vendedor SaaS | `process_seller_subscriptions` |
| Campañas opcionales | `send_marketing_emails` |
| Prueba manual | `send_verification_email` |

---

## Desarrollo local

Sin `RESEND_API_KEY` y con `DEBUG=True`:

```env
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
```

Los mensajes se imprimen en la consola donde corre `runserver`.

Para probar Resend en local, añade la clave y un remitente de sandbox verificado.

---

## Verificación

```bash
python manage.py check_email_env
python manage.py verify_integrations
python manage.py send_verification_email tu@email.com
```

`verify_integrations` comprueba BD, storage y Resend en un solo informe.

---

## Producción (Railway / dominio propio)

1. Verificar dominio `tradeflowcolon.com` en Resend → Domains (SPF/DKIM).
2. Configurar en Railway:

```env
RESEND_API_KEY=re_...
RESEND_FROM_EMAIL=TradeFlow Colón <no-reply@tradeflowcolon.com>
DEFAULT_FROM_EMAIL=TradeFlow Colón <no-reply@tradeflowcolon.com>
PUBLIC_BASE_URL=https://tradeflowcolon.com
REQUIRE_EMAIL_VERIFICATION=true
```

3. Desplegar y enviar un reset de contraseña de prueba.

---

## Documentos deprecados

| Documento | Motivo |
|-----------|--------|
| [SUPABASE_GMAIL.md](SUPABASE_GMAIL.md) | Gmail SMTP solo para laboratorio sin Resend |
| [ENTERPRISE_EMAIL.md](ENTERPRISE_EMAIL.md) | Describía Edge Function Supabase; no está cableada en Django |
| `supabase/functions/send-transactional-email/` | Workaround histórico si Railway bloqueaba SMTP |

**Fuente de verdad:** `core/email_service.py`, `tradeflow_colon/settings.py` y
esta guía.

---

## Registro y depuración

Los envíos registran en el logger `tradeflow.email` (`INFO` éxito, `ERROR` fallo).
En Sentry (si `SENTRY_DSN` está configurado) los errores no capturados también
aparecen en el panel de incidentes.
