# TradeFlow Colón — correo transaccional en producción

La aplicación **no usa Resend**. El envío es:

1. **Supabase Edge Function** (opcional, `SUPABASE_EMAIL_ENABLED=true`)
2. **Gmail SMTP** como respaldo (`EMAIL_HOST_USER` + App Password)
3. **Consola** en desarrollo (`EMAIL_BACKEND` consola)

## Opción A — Supabase Edge Function

```env
SUPABASE_URL=https://TU_PROYECTO.supabase.co
SUPABASE_SERVICE_KEY=eyJ...
SUPABASE_EMAIL_FUNCTION=send-transactional-email
SUPABASE_EMAIL_ENABLED=true
```

Si tu función en Supabase depende de un proveedor que no puedes usar, pon `SUPABASE_EMAIL_ENABLED=false` y usa solo Gmail.

## Opción B — Gmail (recomendado en Railway)

```env
SUPABASE_EMAIL_ENABLED=false
EMAIL_HOST_USER=tu@gmail.com
EMAIL_HOST_PASSWORD=xxxx xxxx xxxx xxxx
DEFAULT_FROM_EMAIL=TradeFlow <tu@gmail.com>
PUBLIC_BASE_URL=https://tuapp.railway.app
```

Usar [App Password](https://myaccount.google.com/apppasswords) con 2FA activado.

## Verificación

```bash
python manage.py verify_integrations --email=tu@correo.com
python manage.py release_check
```

En `DEBUG=False`, `release_check` falla si el backend de correo sigue siendo consola.
