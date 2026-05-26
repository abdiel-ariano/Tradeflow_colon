# TradeFlow Colón — correo transaccional en producción

La aplicación **no debe** usar `console.EmailBackend` en staging/producción.

## Opción A — Resend (recomendado)

En `.env` o variables de entorno:

```env
EMAIL_RESEND_API_KEY=re_xxxxxxxx
DEFAULT_FROM_EMAIL=TradeFlow <onboarding@tudominio.com>
PUBLIC_BASE_URL=https://tuapp.railway.app
```

Resend usa SMTP:

- Host: `smtp.resend.com`
- Puerto: `587` (TLS)
- Usuario: `resend`
- Contraseña: la API key

Django lo configura automáticamente si `EMAIL_RESEND_API_KEY` está definido.

## Opción B — SendGrid

```env
EMAIL_SENDGRID_API_KEY=SG.xxxxxxxx
DEFAULT_FROM_EMAIL=TradeFlow <noreply@tudominio.com>
```

## Opción C — Gmail (desarrollo o bajo volumen)

```env
EMAIL_HOST_USER=tu@gmail.com
EMAIL_HOST_PASSWORD=xxxx xxxx xxxx xxxx
DEFAULT_FROM_EMAIL=TradeFlow <tu@gmail.com>
```

Usar [App Password](https://myaccount.google.com/apppasswords) con 2FA activado.

## Verificación

```bash
python manage.py verify_integrations --email=tu@correo.com
python manage.py release_check
```

En `DEBUG=False`, `release_check` falla si el backend de correo sigue siendo consola.
