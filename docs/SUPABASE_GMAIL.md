# Supabase + Gmail — TradeFlow Colón (menos de 10 pasos)

## Supabase (PostgreSQL)

1. Crea un proyecto en [https://supabase.com](https://supabase.com).
2. Ve a **Settings → Database** y copia la **URI** (modo Session o Transaction).
3. En la raíz del repo: `cp .env.example .env`
4. Pega en `.env`:
   ```env
   DATABASE_URL=postgresql://postgres:TU_CONTRASENA@db.TU_PROYECTO.supabase.co:5432/postgres
   DB_SSL=true
   DB_SSLMODE=require
   ```
5. Instala dependencias: `pip install -r requirements.txt`
6. Aplica migraciones: `python manage.py migrate`
7. Carga demo: `python manage.py cargar_demo`
8. Verifica DB: `python manage.py verify_integrations --skip-email`

Si falla SSL en Windows local con `DEBUG=True`, prueba `DB_SSL=false` o añade `?sslmode=require` a la URI.

## Gmail (SMTP real)

1. Activa **verificación en 2 pasos** en tu cuenta Google.
2. Crea una **Contraseña de aplicación**: [https://myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
3. En `.env`:
   ```env
   EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
   EMAIL_HOST_USER=tu@gmail.com
   EMAIL_HOST_PASSWORD=la-app-password-de-16-caracteres
   DEFAULT_FROM_EMAIL=TradeFlow <tu@gmail.com>
   APPLICATION_REVIEW_EMAILS=tu@gmail.com
   PUBLIC_BASE_URL=http://127.0.0.1:8000
   ```
4. Prueba envío: `python manage.py verify_integrations --email tu@gmail.com`

Si `EMAIL_HOST_USER` y `EMAIL_HOST_PASSWORD` están definidos, el proyecto **elige SMTP automáticamente** aunque no declares `EMAIL_BACKEND`.

## Flujos que usan correo

| Flujo | Cuándo |
|--------|--------|
| Verificación de cuenta | Registro + enlace `/verificar-email/` |
| Solicitud de acceso | POST `/solicitud-acceso/` |
| Revisión solicitud | Enlaces Aprobar/Rechazar en correo a revisores |
| Orden pendiente | Checkout → vendedor recibe aviso |
| Cambio de estado | Vendedor confirma → comprador |

## Producción (Railway / similar)

- Variable `DATABASE_URL` del addon Postgres **o** la URI de Supabase.
- Mismas variables Gmail en el panel de variables (sin subir `.env`).
- `PUBLIC_BASE_URL=https://tu-dominio.up.railway.app`
- `python manage.py collectstatic` en el build.
- `DEBUG=False`, `ALLOWED_HOSTS` con tu dominio.

## Comando único de diagnóstico

```bash
python manage.py verify_integrations --email tu@gmail.com
```

Muestra si Postgres/Supabase responde y si Gmail acepta el envío.
