# TradeFlow Colón — Guía técnica

Marketplace B2B para la **Zona Libre de Colón (Panamá)**: compradores mayoristas
descubren inventario verificado ZLC; vendedores gestionan tienda, planes SaaS y
logística; operadores administran la plataforma.

Proyecto orientado a **Expo Supérate 2026**.

## Arranque rápido (local)

```bash
cp .env.example .env
# Completa al menos: SECRET_KEY, DEBUG=True
# Opcional demo real: DATABASE_URL (Supabase), RESEND_API_KEY, GROQ_API_KEY

python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

python manage.py migrate
python manage.py cargar_demo          # empresas, productos y usuarios demo
python manage.py createsuperuser      # opcional
python manage.py runserver
```

Abre **http://127.0.0.1:8000**

Guía Supabase + correo: [docs/SUPABASE_GMAIL.md](docs/SUPABASE_GMAIL.md)

---

## Arquitectura (estado actual)

```
.
├── manage.py                 # CLI Django
├── requirements.txt          # Dependencias (pins de seguridad)
├── tradeflow_colon/          # Proyecto Django
│   ├── settings.py           # Env, auth, CSP, Supabase, email, SaaS
│   ├── urls.py               # Admin, i18n, health, include core
│   ├── wsgi.py / asgi.py     # Entrada Gunicorn / async
├── core/                     # App principal del marketplace
│   ├── models.py             # Company, Product, Order, RFQ, perfiles…
│   ├── enterprise_models.py  # SaaS seller, ads, API keys, logística
│   ├── views*.py             # Catálogo, auth, portales, checkout…
│   ├── utils/                # Email, OTP, billing, media, i18n…
│   ├── middleware/           # Seguridad, i18n, onboarding gate
│   ├── templatetags/         # Dinero, media, CSP, catálogo
│   ├── management/commands/  # Seeds, verify, cleanup, demos
│   └── tests/                # Pruebas de flujo y regresiones
├── analytics/                # KPIs, forecasts y chat IA del seller
├── templates/                # HTML (marketplace público + portales)
├── static/                   # CSS/JS del design system TradeFlow
├── frontend/admin-saas/      # Panel admin SaaS (Vite)
├── supabase/                 # Edge functions / notas de storage
└── docs/                     # Guías técnicas (email, storage, AI…)
```

### Roles de negocio

| Rol | Capacidad principal |
|-----|---------------------|
| Comprador (buyer) | Catálogo, carrito, RFQ, checkout, órdenes |
| Vendedor (seller) | Mi Tienda, inventario, planes SaaS, analítica |
| Transportista | Portal logístico / envíos |
| Admin | Django admin + métricas de plataforma |

---

## URLs útiles

| Ruta | Descripción |
|------|-------------|
| `/` | Home marketplace |
| `/catalogo/` | Catálogo público mayorista |
| `/carrito/` | Carrito / inquiry |
| `/login/`, `/signup/` | Auth (también OAuth si está configurado) |
| `/mi-tienda/` | Portal vendedor |
| `/dashboard/` | Panel operativo (según rol) |
| `/admin/` | Django Admin |
| `/health/live/`, `/health/ready/` | Probes Railway |

---

## Stack técnico

- **Backend:** Django 6, PostgreSQL (Supabase) o SQLite local
- **Auth:** Django + allauth (Google/Microsoft), OTP email, django-axes
- **Seguridad:** Argon2, CSRF, CSP nonce, HSTS en prod (`SECURITY.md`)
- **Media:** filesystem local o Supabase Storage
- **Email:** Resend (transaccional)
- **IA:** Groq (asistente / analytics)
- **Deploy:** Gunicorn + WhiteNoise (Railway)

Paleta y UI: ver [DESIGN.md](DESIGN.md) (navy `#0F2A44`, orange `#F26522`, primary `#0057A8`).

---

## Documentación adicional

| Documento | Contenido |
|-----------|-----------|
| [SECURITY.md](SECURITY.md) | Política de vulnerabilidades y hardening |
| [PRODUCT.md](PRODUCT.md) | Propósito de producto y principios |
| [DESIGN.md](DESIGN.md) | Tokens y lenguaje visual |
| [docs/DEMO_DATA_POLICY.md](docs/DEMO_DATA_POLICY.md) | Aviso y retiro de datos simulados |
| [docs/AFICHE_TECNICO.md](docs/AFICHE_TECNICO.md) | Afiche técnico: stack, roles y relaciones |
| [docs/](docs/) | Supabase, storage, AI search, email enterprise |

---

## Comandos frecuentes

```bash
python manage.py test core.tests          # suite principal
python manage.py verify_integrations      # chequeo email/Supabase
python manage.py cleanup_sparse_demo_companies --dry-run
python manage.py check
```

---

*TradeFlow Colón — Expo Supérate 2026 · Zona Libre de Colón, Panamá*

