# Documentación técnica — TradeFlow Colón

Marketplace mayorista B2B para la **Zona Libre de Colón (Panamá)**. Los compradores
exploran catálogos verificados, carrito y solicitudes de cotización (RFQ); los
vendedores operan tienda, planes SaaS y logística; el equipo interno usa Django
Admin y paneles operativos.

**Stack:** Django 6 · PostgreSQL (Supabase o AWS RDS) · Resend · Groq (opcional)
· PWA + Android TWA · despliegue principal en **Railway**.

---

## 1. Estructura del repositorio

```
manage.py                     # CLI Django
tradeflow_colon/              # Proyecto (settings, urls, wsgi/asgi)
core/                         # App principal del marketplace
  models.py                   # Empresa, producto, orden, RFQ, perfiles
  enterprise_models.py        # SaaS vendedor, anuncios, API keys
  views/                      # Vistas HTTP por dominio (catálogo, auth, seller…)
  utils/                      # Servicios transversales (email, OTP, media, i18n)
  middleware/                 # Seguridad, i18n, onboarding, MFA staff
  email_service.py            # Envío transaccional vía Resend
  management/commands/        # Seeds, verificación, cron de negocio
analytics/                    # KPIs y analítica IA del vendedor
templates/                    # HTML (marketplace, portales, emails)
static/                       # CSS/JS del design system
frontend/admin-saas/          # Panel admin SaaS (React/Vite)
locale/                       # Traducciones django.po (en, es)
android/                      # Manifest Bubblewrap (TWA)
docs/                         # Esta documentación
```

---

## 2. Base de datos

| Entorno | Motor | Configuración |
|---------|-------|----------------|
| Local rápido | SQLite | Sin `DATABASE_URL` |
| Demo / staging / prod | PostgreSQL | `DATABASE_URL` en `.env` |

- Normalización de URL: `core/utils/database_url.py`
- SSL: `DB_SSL=true`, `DB_SSLMODE=require` (Supabase)
- Pooler Supabase recomendado en Railway (puerto 6543 transaction)
- Migraciones: `python manage.py migrate`
- Seed demo: `python manage.py cargar_demo`
- Verificación: `python manage.py check_database`, `verify_integrations`

Guía detallada: [BASE_DE_DATOS.md](BASE_DE_DATOS.md).

---

## 3. Correo transaccional (Resend)

**Canal de producción:** API HTTP de [Resend](https://resend.com) vía
`core/email_service.py`.

| Variable | Uso |
|----------|-----|
| `RESEND_API_KEY` | Clave API (obligatoria en prod) |
| `RESEND_FROM_EMAIL` / `DEFAULT_FROM_EMAIL` | Remitente verificado en Resend |
| `PUBLIC_BASE_URL` | Enlaces absolutos (reset password, verificación) |
| `REQUIRE_EMAIL_VERIFICATION` | OTP al registrarse |

**Flujos que envían correo:**

- Verificación de email (OTP)
- Restablecimiento de contraseña
- Notificaciones de suscripción vendedor (`process_seller_subscriptions`)
- Marketing opcional (`send_marketing_emails`)

**Local sin Resend:** con `DEBUG=True` y sin clave, el fallback es
`EMAIL_BACKEND=console` (salida en terminal).

**No usar en producción:** Gmail SMTP ni la Edge Function de Supabase documentada
en guías antiguas; ver [CORREO_TRANSACCIONAL.md](CORREO_TRANSACCIONAL.md).

Comandos de diagnóstico:

```bash
python manage.py check_email_env
python manage.py verify_integrations
python manage.py send_verification_email usuario@ejemplo.com
```

---

## 4. Internacionalización (i18n)

| Aspecto | Valor actual |
|---------|----------------|
| Idioma por defecto | Inglés (`LANGUAGE_CODE = 'en'`) |
| Idiomas soportados | `en`, `es` |
| URLs | Español sin prefijo; inglés bajo `/en/` |
| Archivos | `locale/en/LC_MESSAGES/`, `locale/es/LC_MESSAGES/` |
| Middleware | `core/middleware/tf_i18n.py` |
| Cambio de idioma | `POST /i18n/setlang/` |

Auditoría de cadenas:

```bash
python scripts/i18n_audit.py
python manage.py compilemessages
```

Guía: [INTERNACIONALIZACION.md](INTERNACIONALIZACION.md).

---

## 5. Autenticación y roles

- Django auth + **django-allauth** (Google, Microsoft, LinkedIn si hay credenciales)
- **django-axes** — bloqueo por intentos fallidos
- **Argon2** — hash de contraseñas
- Roles de negocio: comprador, vendedor, admin (vía perfiles y permisos)
- MFA TOTP para staff: `STAFF_MFA_REQUIRED`
- Verificación email: `REQUIRE_EMAIL_VERIFICATION`

Variables OAuth en `.env.example`: `GOOGLE_*`, `MICROSOFT_*`, `LINKEDIN_*`.

---

## 6. Media e imágenes

| Backend | Cuándo |
|---------|--------|
| Filesystem local | `SERVE_LOCAL_MEDIA=true` (desarrollo) |
| Supabase Storage | `SUPABASE_URL` + `SUPABASE_SERVICE_KEY` |
| AWS S3 | `AWS_MEDIA_BUCKET_NAME` (prioridad en AWS) |

Implementación Supabase: `core/storage/supabase_media.py`.  
Guía: [SUPABASE_STORAGE.md](SUPABASE_STORAGE.md).

---

## 7. PWA y Android

| Recurso | Ruta / archivo |
|---------|----------------|
| Manifest | `/manifest.webmanifest` → `core/views_platform.py` |
| Service worker | `/service-worker.js` |
| Iconos PWA | `/pwa/icon-192.png`, `/pwa/icon-512.png` |
| Digital Asset Links | `/.well-known/assetlinks.json` |
| TWA / APK | `android/twa-manifest.json`, workflow `android-apk.yml` |
| CSS móvil | `static/css/tf-mobile-pwa.css` |

Guía completa: [ANDROID_APK.md](ANDROID_APK.md).

---

## 8. Caché y rendimiento

- Producción: `REDIS_URL` recomendado
- Alternativa: tabla de caché en PostgreSQL (`USE_DB_CACHE=true`)
- TTLs configurables: `CACHE_TTL_*` en `.env`
- Política HTTP: [PAGE_CACHE.md](PAGE_CACHE.md)
- Implementación: `core/utils/tradeflow_cache.py`, `signals_cache.py`

---

## 9. IA (opcional)

- **Groq** — asistente TF en navbar y analítica del vendedor
- Variables: `GROQ_API_KEY`, `GROQ_MODEL`, `ANALYTICS_LLM_MODEL`
- Búsqueda typeahead: [AI_SEARCH.md](AI_SEARCH.md) (`core/views/home_map.py`)

---

## 10. Despliegue

| Componente | Detalle |
|------------|---------|
| Imagen | `Dockerfile` (Python 3.12, Gunicorn) |
| Entrypoint | `scripts/docker-entrypoint.sh` (migrate, collectstatic, gunicorn) |
| Railway | `railway.json`, health `/health/live/` |
| CI | `.github/workflows/ci.yml` (tests, Bandit, pip-audit, admin-saas build) |
| AWS alternativo | `infra/aws/p0-stack.yaml`, [MIGRACION_DB_AWS_RDS.md](MIGRACION_DB_AWS_RDS.md) |

**Producción mínima:**

```bash
DEBUG=false
SECRET_KEY=<fuerte>
DATABASE_URL=<postgres>
RESEND_API_KEY=<resend>
ALLOWED_HOSTS=tradeflowcolon.com,www.tradeflowcolon.com
PUBLIC_BASE_URL=https://tradeflowcolon.com
```

Runbook: [SECURITY_OPS.md](SECURITY_OPS.md).

---

## 11. Cron y tareas programadas (Railway)

| Schedule | Comando | Propósito |
|----------|---------|-----------|
| `0 6 * * *` | `process_seller_subscriptions` | Trial, renovación, gracia, emails |
| `0 4 * * 0` | `purge_security_logs --days 90` | Retención logs seguridad |

---

## 12. Datos demo y Expo

- `python manage.py cargar_demo` — empresas, productos, usuarios demo
- `DEMO_CATALOG_DISCLOSURE=true` — banner DEMO en UI
- `EXPO_DEMO_MODE` — relaja algunas compuertas en feria (ver `.env.demo`)
- Política: [DEMO_DATA_POLICY.md](DEMO_DATA_POLICY.md)

**Usuarios demo típicos:**

| Rol | Usuario | Contraseña |
|-----|---------|------------|
| Comprador | `demo_buyer` | `Demo1234!` |
| Vendedor | `demo_seller` | `Demo1234!` |
| Admin | `demo_admin` | `Demo1234!` |

---

## 13. Pruebas

```bash
python manage.py check
python manage.py test core.tests
python manage.py verify_integrations
cd frontend/admin-saas && npm ci && npm run build
```

Estándares: [CALIDAD_CODIGO.md](CALIDAD_CODIGO.md).

---

## 14. Referencia rápida de URLs

| Ruta | Descripción |
|------|-------------|
| `/` | Home marketplace |
| `/catalogo/` | Catálogo público |
| `/carrito/` | Carrito / inquiry |
| `/login/`, `/signup/` | Autenticación |
| `/mi-tienda/` | Portal vendedor |
| `/dashboard/` | Panel operativo |
| `/admin/` | Django Admin |
| `/health/live/`, `/health/ready/` | Probes |

---

*TradeFlow Colón — documentación mantenida por el equipo de desarrollo.
Ante conflicto entre guías, prevalecen `settings.py`, `.env.example` y este documento.*
