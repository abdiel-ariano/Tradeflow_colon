# TradeFlow Colón — Guía técnica

Marketplace B2B para la **Zona Libre de Colón (Panamá)**: compradores mayoristas
descubren inventario verificado ZLC; vendedores gestionan tienda, planes SaaS y
logística; operadores administran la plataforma.

Proyecto orientado a **Expo Supérate 2026** · producción en `tradeflowcolon.com`.

## Arranque rápido (local)

```bash
cp .env.example .env
# Completa al menos: SECRET_KEY, DEBUG=True
# Demo real: DATABASE_URL (Supabase), RESEND_API_KEY, GROQ_API_KEY

python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

python manage.py migrate
python manage.py cargar_demo          # empresas, productos y usuarios demo
python manage.py createsuperuser      # opcional
python manage.py runserver
```

Abre **http://127.0.0.1:8000**

| Recurso | Enlace |
|---------|--------|
| Documentación completa | [docs/DOCUMENTACION_TECNICA.md](docs/DOCUMENTACION_TECNICA.md) |
| Índice de guías | [docs/README.md](docs/README.md) |
| Variables de entorno | [.env.example](.env.example) |
| Base de datos | [docs/BASE_DE_DATOS.md](docs/BASE_DE_DATOS.md) |
| Correo (Resend) | [docs/CORREO_TRANSACCIONAL.md](docs/CORREO_TRANSACCIONAL.md) |
| Calidad / PEP 8 | [docs/CALIDAD_CODIGO.md](docs/CALIDAD_CODIGO.md) |

---

## Arquitectura (estado actual)

```
.
├── manage.py                 # CLI Django
├── requirements.txt          # Dependencias (pins de seguridad)
├── tradeflow_colon/          # Proyecto Django (settings, urls, wsgi)
├── core/                     # App principal del marketplace
│   ├── models.py             # Company, Product, Order, RFQ, perfiles…
│   ├── enterprise_models.py  # SaaS seller, ads, API keys, logística
│   ├── views/                # Catálogo, auth, portales, PWA, home…
│   ├── email_service.py      # Correo transaccional Resend
│   ├── utils/                # Email, OTP, billing, media, i18n…
│   ├── middleware/           # Seguridad, i18n, onboarding gate
│   ├── management/commands/  # Seeds, verify, cleanup, demos
│   └── tests/                # Pruebas de flujo y regresiones
├── analytics/                # KPIs, forecasts y chat IA del seller
├── locale/                   # Traducciones en/es (gettext)
├── templates/                # HTML marketplace + portales
├── static/                   # CSS/JS (tf-mobile-pwa, home-alibaba…)
├── frontend/admin-saas/      # Panel admin SaaS (Vite/React)
├── android/                  # TWA Bubblewrap
└── docs/                     # Documentación técnica en español
```

Inventario detallado de módulos: [docs/INVENTARIO_MODULOS.md](docs/INVENTARIO_MODULOS.md).

### Roles de negocio

| Rol | Capacidad principal |
|-----|---------------------|
| Comprador (buyer) | Catálogo, carrito, RFQ, checkout, órdenes |
| Vendedor (seller) | Mi Tienda, inventario, planes SaaS, analítica |
| Admin | Django admin + métricas de plataforma |

### Usuarios demo

| Rol | Usuario | Contraseña |
|-----|---------|------------|
| Comprador | `demo_buyer` | `Demo1234!` |
| Vendedor | `demo_seller` | `Demo1234!` |
| Admin | `demo_admin` | `Demo1234!` |

---

## URLs útiles

| Ruta | Descripción |
|------|-------------|
| `/` | Home marketplace |
| `/catalogo/` | Catálogo público mayorista |
| `/carrito/` | Carrito / inquiry |
| `/login/`, `/signup/` | Auth (+ OAuth si está configurado) |
| `/mi-tienda/` | Portal vendedor |
| `/dashboard/` | Panel operativo (según rol) |
| `/admin/` | Django Admin |
| `/en/…` | Misma app en inglés (español sin prefijo por defecto UI en EN) |
| `/health/live/`, `/health/ready/` | Probes Railway |
| `/manifest.webmanifest` | PWA manifest |

i18n: [docs/INTERNACIONALIZACION.md](docs/INTERNACIONALIZACION.md).

---

## Stack técnico

- **Backend:** Django 6, PostgreSQL (Supabase/RDS) o SQLite local
- **Auth:** Django + allauth (Google/Microsoft/LinkedIn), OTP email, django-axes
- **Seguridad:** Argon2, CSRF, CSP nonce, HSTS en prod (`SECURITY.md`)
- **Media:** filesystem local, Supabase Storage o AWS S3
- **Email:** **Resend** (transaccional — OTP, reset, SaaS)
- **IA:** Groq (asistente / analytics) — opcional
- **Móvil:** PWA + Android TWA (`docs/ANDROID_APK.md`, `tf-mobile-pwa.css`)
- **Deploy:** Gunicorn + WhiteNoise (Railway)

Paleta y UI: [DESIGN.md](DESIGN.md) (navy `#0F2A44`, orange `#F26522`, primary `#0057A8`).

---

## Documentación adicional

| Documento | Contenido |
|-----------|-----------|
| [docs/README.md](docs/README.md) | Índice maestro de toda la documentación |
| [docs/DOCUMENTACION_TECNICA.md](docs/DOCUMENTACION_TECNICA.md) | BD, correo, i18n, PWA, despliegue |
| [SECURITY.md](SECURITY.md) | Política de vulnerabilidades |
| [PRODUCT.md](PRODUCT.md) | Propósito de producto (inglés) |
| [DESIGN.md](DESIGN.md) | Tokens y lenguaje visual |
| [CHANGELOG.md](CHANGELOG.md) | Historial de cambios |
| [docs/MENU_MOVIL_ANDROID.md](docs/MENU_MOVIL_ANDROID.md) | Menú hamburguesa móvil, diagnóstico Android y pruebas |

---

## Comandos frecuentes

```bash
python manage.py test core.tests          # suite principal
python manage.py verify_integrations      # BD + storage + Resend
python manage.py check_email_env          # variables de correo
python manage.py cleanup_sparse_demo_companies --dry-run
python manage.py check
python scripts/i18n_audit.py              # auditoría cadenas i18n
```

---

*TradeFlow Colón — Expo Supérate 2026 · Abdiel Ariano*
