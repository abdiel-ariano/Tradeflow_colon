# Inventario de módulos Python — TradeFlow Colón

Mapa de paquetes y responsabilidades. Docstrings de cada módulo deben seguir
[CALIDAD_CODIGO.md](CALIDAD_CODIGO.md) (PEP 257, español).

---

## `tradeflow_colon/` — proyecto Django

| Archivo | Responsabilidad |
|---------|-----------------|
| `settings.py` | Configuración central: BD, email Resend, i18n, OAuth, caché, PWA, SaaS |
| `urls.py` | Admin, health, PWA, `i18n_patterns` → `core.urls` |
| `wsgi.py` / `asgi.py` | Entrada Gunicorn / ASGI |
| `__init__.py` | Marca del paquete proyecto |

---

## `core/` — marketplace

### Modelos y datos

| Archivo | Responsabilidad |
|---------|-----------------|
| `models.py` | Empresa, producto, orden, RFQ, carrito, perfiles comprador/vendedor |
| `enterprise_models.py` | Planes SaaS, suscripciones, anuncios, API keys, logística |
| `admin.py` | Personalización Django Admin |

### Vistas HTTP (`core/views/`)

| Módulo | Dominio |
|--------|---------|
| `auth_session.py` | Login, logout, sesión |
| `catalog_cart.py` | Catálogo público, carrito, inquiry |
| `public_pages.py` | Home, about, páginas estáticas marketplace |
| `seller_store.py` | Portal vendedor, mi tienda |
| `admin_ops.py` | Dashboard operativo interno |
| `home_map.py` | Home, mapa ZLC, búsqueda IA typeahead |
| `__init__.py` | Reexporta API pública de vistas |

Vistas adicionales en raíz `core/`: `views_i18n.py`, `views_platform.py` (PWA),
`views_seller_onboarding.py`, `views_social.py`, etc.

### Servicios transversales

| Archivo / carpeta | Responsabilidad |
|-------------------|-----------------|
| `email_service.py` | Correo transaccional Resend (OTP, etc.) |
| `android_assetlinks.py` | `assetlinks.json` dinámico para TWA |
| `context_processors.py` | Carrito, i18n JS, demo banner, CSP nonce |
| `middleware/` | Seguridad CSP, i18n URL, onboarding gate, MFA staff, BD caída |
| `storage/supabase_media.py` | Backend Django storage Supabase/S3 |
| `utils/` | ~57 módulos: OTP, billing, media, PDF, caché, seller lifecycle… |
| `templatetags/` | Dinero, media, catálogo, CSP, marca |
| `signals_cache.py` | Invalidación de caché |
| `signals_enterprise.py` | Hooks modelo enterprise |
| `social_auth.py` | Adaptadores django-allauth |

### Comandos `manage.py` (`core/management/commands/`)

| Comando | Descripción |
|---------|-------------|
| `cargar_demo` | Seed principal demo (empresas, productos, usuarios) |
| `cargar_demo_merchandising` | Merchandising adicional demo |
| `seed_enterprise` / `seed_enterprise_year` | Catálogo enterprise masivo |
| `seed_catalog_images` | Asigna fotos de categoría a productos |
| `verify_integrations` | Chequeo BD + storage + Resend |
| `check_database` | Preflight conexión BD (Docker entrypoint) |
| `check_email_env` | Variables de correo |
| `check_media_storage` | Bucket y permisos media |
| `send_verification_email` | Prueba OTP a un email |
| `process_seller_subscriptions` | Cron SaaS vendedor |
| `purge_security_logs` | Retención logs seguridad |
| `release_check` | Checklist pre-release |
| `cleanup_sparse_demo_companies` | Limpieza empresas demo vacías |
| `verify_saas` | Integridad datos SaaS |
| `sync_admin_permissions` | Permisos admin |
| `reset_staff_mfa` | Reset TOTP staff |
| `load_demo_images` / `generate_placeholders` | Assets de imagen demo |
| `actualizar_merchandising` | Actualiza merchandising home |
| `verificar_cuentas_demo` | Estado cuentas demo |

---

## `analytics/` — analítica vendedor

| Módulo | Responsabilidad |
|--------|-----------------|
| `views.py` | UI analítica `/mi-tienda/analitica/` |
| `engine/` | Carga datos, gráficas, forecast, LLM Groq |
| `data_source.py` | Acceso a datos para dashboards |

---

## `scripts/` — herramientas CLI (fuera de Django)

| Script | Uso |
|--------|-----|
| `bootstrap_dotenv.py` | Genera `.env` inicial |
| `i18n_audit.py` | Auditoría cadenas sin traducir |
| `fill_spanish_translations.py` | Relleno asistido `django.po` |
| `verify_csp.py` | Verificación CSP en templates |
| `docker-entrypoint.sh` | Migrate + Gunicorn en producción |
| `aws/*.sh` | Export/restore BD, media |
| `record_mobile_demo.js` | QA visual viewport móvil |

---

## Pruebas

| Ubicación | Alcance |
|-----------|---------|
| `core/tests/` | ~102 archivos: marketplace, auth, i18n, PWA, SaaS, PDP… |
| `analytics/tests/` | Gráficas y analítica seller |

Ejecutar: `python manage.py test core.tests`

---

## Plantillas y estáticos

| Ruta | Contenido |
|------|-----------|
| `templates/core/` | Marketplace, auth, seller, emails |
| `templates/pwa/` | Service worker |
| `static/css/` | Design system, home-alibaba, tf-mobile-pwa |
| `static/js/` | tf-mobile-pwa.js, carrito, home marketplace |
| `locale/` | Traducciones gettext |

Documentación de assets: `static/img/README.md`, `static/assets/products/README.md`.

---

## Configuración de despliegue

| Archivo | Rol |
|---------|-----|
| `Dockerfile` | Imagen producción |
| `railway.json` | Servicio Railway |
| `.github/workflows/ci.yml` | CI principal |
| `.github/workflows/android-apk.yml` | Build APK/AAB |
| `infra/aws/p0-stack.yaml` | Stack AWS opcional |

Ver [DOCUMENTACION_TECNICA.md](DOCUMENTACION_TECNICA.md) para el mapa completo
de variables de entorno.
