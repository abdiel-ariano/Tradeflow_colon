# TradeFlow Colón — Codebase Diagnostic

High-level map for onboarding and maintenance. Generated as part of the search/typeahead documentation pass.

## What this project is

Django 6 monolith for a B2B/B2C wholesale marketplace (Colón Free Zone, Panama):

- Public catalog and marketing home
- Buyer cart, checkout, RFQ, orders
- Seller portal (products, sales, quotes, SaaS plans)
- Admin dashboard + React SaaS shell at `/saas/`
- Optional Supabase (DB/media), Resend (email), Groq (AI assist/search)

## Top-level layout

| Path | Purpose |
|------|---------|
| `tradeflow_colon/` | Settings, root URLs, WSGI |
| `core/` | Single Django app — models, views, middleware, utils, tests |
| `templates/core/` | Server-rendered HTML |
| `static/` | CSS, JS, images; `admin-saas/` built from React |
| `locale/` | gettext `en` / `es` |
| `frontend/admin-saas/` | React admin dashboard → `/saas/` |
| `frontend/marketplace/` | Separate TanStack demo (not main cart) |
| `docs/` | Integration guides (Supabase, email, this file) |
| `scripts/` | Bootstrap, deploy, CSP checks |

## Request routing

- **i18n:** `prefix_default_language=False` → English unprefixed, Spanish under `/es/`.
- **Entry:** `tradeflow_colon/urls.py` mounts `core.urls` inside `i18n_patterns`.
- **Health:** `/health/live/`, `/health/ready/`.
- **Language:** `/i18n/setlang/` → `core/views_i18n.set_language`.

### Role surfaces

| Role | Examples |
|------|----------|
| Public | `/`, `/catalogo/`, `/login/`, legal pages |
| Buyer | `/carrito/`, `/checkout/`, `/mis-ordenes/`, `/cotizaciones/` |
| Seller | `/mi-tienda/`, products, sales, plan, reporting |
| Admin | `/dashboard/`, `/productos/`, `/panel/applications/`, `/saas/` |
| API | `/api/search/suggest/`, `/api/asistente/`, `/api/v1/*` |

## `core/` module map

| Module | Responsibility |
|--------|----------------|
| `models.py` | Product, Order, Company, UserProfile, cart, shipments |
| `enterprise_models.py` | SaaS plans, billing, API keys |
| `views.py` | Large view module (~5k lines): home, buyer, APIs |
| `views_seller_pages.py` | Seller shell pages |
| `auth_views.py` | OTP email verification |
| `decorators.py` | `buyer_required`, role gates |
| `middleware/` | i18n redirect, onboarding gate, CSP, rate limit |
| `merchandising.py` | Home/catalog featured content |
| `utils/ai_search.py` | Typeahead suggestion engine |
| `utils/i18n_urls.py` | Language-prefixed URL helpers |
| `email_service.py` | Resend transactional mail |
| `management/commands/` | Demo seed, release checks |

## Template hierarchy

```
base.html
├── marketplace_public_navbar (home, catalog marketing)
├── buyer/buyer_navbar (authenticated buyer)
├── seller_layout.html (seller sidebar)
└── page templates (carrito, checkout, dashboard, …)
```

Nav is chosen in `base.html` from `request.user.profile.role`.

## Frontend conventions

- **CSS:** `tf-*` design system, `catalog*`, `home-*`, `seller_*`
- **JS:** page modules (`cart_ajax.js`, `catalogo-publico.js`) + shared `tf-ai-search.js`
- **Cache bust:** `?v={{ tf_asset_version }}`
- **CSP:** nonces on inline scripts (`csp_nonce` context processor)

## Testing

- **Location:** `core/tests/` (50+ modules)
- **CI:** runs `test_flujo_compra` + Django checks (not full suite)
- **Pattern:** `@override_settings(REQUIRE_EMAIL_VERIFICATION=False, …)`

## i18n

- Default language: English (`LANGUAGE_CODE = 'en'`)
- PO files: `locale/en/LC_MESSAGES/django.po`, `locale/es/...`
- JS strings: `TF_I18N` dict from `core/context_processors.tf_i18n`
- Templates: `{% trans %}` with English msgids

## Known technical debt (short)

1. `core/views.py` monolith — split by domain when touching heavily.
2. README outdated vs current marketplace scope.
3. Duplicate URL names in `core/urls.py` for some routes.
4. Legacy seller `*-legacy/` paths kept for compat.
5. Two frontend stacks (Django session cart vs `frontend/marketplace` Supabase).
6. CI does not run full test suite.
7. Some PO entries still fuzzy/empty.

## First files to read (new developer)

1. `.env.example`
2. `tradeflow_colon/settings.py`
3. `core/urls.py`
4. `core/models.py`
5. `core/decorators.py` + `core/utils/access_gating.py`
6. `core/middleware/onboarding_gate.py`
7. `templates/core/base.html`
8. `core/context_processors.py`
9. `core/merchandising.py`
10. `core/tests/test_flujo_compra.py`
11. `docs/AI_SEARCH.md` (this feature)
12. `docs/SUPABASE_GMAIL.md` (email/media)

## Environment flags (common)

| Variable | Effect |
|----------|--------|
| `RESEND_API_KEY` | Transactional email |
| `GROQ_API_KEY` | AI assistant + search enrichment |
| `REQUIRE_EMAIL_VERIFICATION` | OTP gate on checkout |
| Supabase storage settings | Remote product images |

---

For feature-specific docs see also `docs/SUPABASE_GMAIL.md` and inline module docstrings in `core/utils/`.
