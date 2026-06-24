# TradeFlow Colón — Public Shell Diagnosis

**Generated:** 2026-05-26 (baseline before final landing polish)  
**Branch:** `cursor/tf-public-landing-ae01`

---

## 1. Public template files (`templates/core/`)

| File | Role |
|------|------|
| `base.html` | Master layout: nav by role, footer, global inline CSS, chat widget |
| `home.html` | Public landing orchestrator |
| `catalogo_publico.html` | Public wholesale catalog |
| `catalogo_publico_partial.html` | AJAX partial wrapper |
| `catalogo_producto_detail.html` | Public product detail (PDP) |
| `login.html` | Guest login |
| `signup.html` | Guest registration |
| `solicitud_acceso.html` | Enterprise access request |
| `legal_terminos.html` | Terms of use |
| `legal_privacidad.html` | Privacy policy |
| `legal_cookies.html` | Cookie policy |
| `visitante_zlc_verificacion.html` | QR visitor verification |
| `includes/public_navbar.html` | Guest Amazon-style header |
| `includes/tf_header_search.html` | Header search form |
| `includes/hero_section.html` | Hero + stats + ship |
| `includes/home_grid.html` | 4-column explore grid |
| `includes/home_products_section.html` | Featured + bestsellers |
| `includes/home_companies_section.html` | Verified companies grid |
| `includes/home_features_section.html` | Why / How it works / CTA |
| `includes/catalogo_publico_results.html` | Catalog grid + pagination |
| `includes/product_card_unified.html` | Shared product card |
| `includes/skeletons/*.html` | Loading skeletons |
| `includes/tf_logo.html` | Brand logo variants |
| `includes/legal_page_styles.html` | Legal page styles |

**Buyer shell (authenticated buyers, not guest):** `includes/buyer/buyer_navbar.html`, `includes/buyer_navbar.html` (alternate).

---

## 2. Public static assets

### CSS (`static/css/`)

| File | Serves public? |
|------|----------------|
| `tf-design-tokens.css` | Yes — all pages via `base.html` |
| `tf-design-system.css` | Yes |
| `tf-components.css` | Yes (PDP, cards) |
| `tf-public-shell.css` | Yes — hero, home grid |
| `tf-header.css` | Yes — guest header |
| `tf-footer.css` | Yes — footer |
| `tf-home-v2.css` | Yes — home sections |
| `tf-skeletons.css` | Yes — home, catalog, PDP |
| `tf-hero-ship.css` | Yes — hero ship (prior implementation) |
| `catalogo-publico.css` | Yes — catalog page |
| `tf-brand.css` | Auth pages |
| `tf-buyer-shell.css` | Loaded globally (overhead for guests) |

### JS (`static/js/`)

| File | Serves public? |
|------|----------------|
| `tf-header.js` | Yes — guest header |
| `tf-skeletons.js` | Yes — home, catalog, PDP |
| `tf_animations.js` | Legacy animations |

### Missing at baseline (requested in polish)

| File | Exists? |
|------|---------|
| `static/css/tf-hero-animations.css` | **No** (had `tf-hero-ship.css` instead) |
| `static/js/tf_hero_animations.js` | **No** (inline in `home.html`) |
| `static/css/tf-sections.css` | **No** |
| `static/js/tf_reveal.js` | **No** |
| `static/js/tf_countup.js` | **No** (inline count-up in `home.html`) |

---

## 3. Spanish text by public template (baseline)

### `includes/public_navbar.html`
- `Zona Libre CFZ`, `Iniciar sesión`, `Crear cuenta`, `Inicia sesión para ver el carrito`
- `Buscar`, `Menú`, `Categorías`, `Ver catálogo completo`, `Todas las categorías →`
- `Ofertas`, `Empresas verificadas`, `Cómo funciona`, `Catálogo mayorista`, `Vender en TradeFlow`
- Drawer: `Catálogo completo`, `Cuenta`, `Menú de navegación`

### `includes/tf_header_search.html`
- `Buscar en el catálogo`, placeholder `Buscar productos, empresas o categorías…`, `aria-label="Buscar"`

### `base.html` footer
- Full footer in Spanish: `Compradores`, `Cómo comprar`, `Catálogo`, `próximamente`, `Vendedores`, `Términos`, `Privacidad`, `Todos los derechos reservados`, `Selección de idioma`, `Español — próximamente`

### `catalogo_publico.html`
- ~100% Spanish UI: `Filtros`, `Buscar`, `Catálogo Zona Libre de Colón`, filter labels, sort options, `Aplicar filtros`, etc.

### `includes/catalogo_publico_results.html`
- `Paginación del catálogo`, `Página anterior/siguiente`, `No encontramos productos`, `Ver todo el catálogo`

### `catalogo_producto_detail.html`
- `Inicio`, `Catálogo`, `Desde`, `Regístrate para ver precios mayoristas`, `Crear cuenta`, `Iniciar sesión`
- Tabs: `Descripción`, `Especificaciones`, `Empresa`, spec labels in Spanish
- `Ver catálogo del proveedor`, `Productos relacionados`, `Ver categoría`

### `includes/product_card_unified.html`
- `Ver detalles →` (mixed with English badges)

### `includes/hero_section.html` (post PR #149)
- **Already English** at baseline of this branch

### `home_*_section.html` (except features partial Spanish anchor)
- Mostly English; `#como-funciona` anchor id is Spanish

### `signup.html`
- Wrong title: `Store — TradeFlow Colón`; form body English

---

## 4. `tf-design-tokens.css` load status

- **Exists:** `static/css/tf-design-tokens.css` (386 lines)
- **Loaded in `base.html` line 23:**  
  `<link rel="stylesheet" href="{% static 'css/tf-design-tokens.css' %}?v=...">`
- All pages extending `base.html` receive tokens.

---

## 5. Asset verification

| Check | Result |
|-------|--------|
| `tf-hero-animations.css` | Missing → use `tf-hero-ship.css` |
| `tf_hero_animations.js` | Missing → inline in `home.html` |
| `tf-sections.css` | Missing |
| `tf_reveal.js` | Missing |
| Ship image path | `{% static 'img/ship-cargo.svg' %}` in `hero_section.html` (no PNG) |
| `product_card_unified.html` | **Yes** — used in `home_products_section.html` and `catalogo_publico_results.html` |

---

## 6. Functional checks (baseline)

| Feature | Status |
|---------|--------|
| `/catalogo/` without login | OK |
| `/catalogo/producto/<id>/` without login | OK |
| Header search → `/catalogo/?buscar=` | OK |
| Catalog filters + AJAX partial | OK |
| Hero metrics from ORM | OK (`merchandising.home_stats()`) |
| Footer without `href="#"` | OK (placeholders use `<span>`) |

---

## 7. Critical issues (priority)

| ID | Priority | Issue |
|----|----------|-------|
| 1 | P0 | Mixed ES/EN: Spanish nav/footer + English home sections |
| 2 | P0 | Catalog + PDP templates entirely/mostly Spanish |
| 3 | P1 | `product_card_unified.html` mixed language |
| 4 | P1 | Hero stats UI outdated vs new design spec |
| 5 | P1 | Ship animation in `tf-hero-ship.css`, not spec `tf-hero-animations.css` |
| 6 | P2 | ~960 lines inline CSS in `base.html` on every page |
| 7 | P2 | Duplicate `catalogo/` routes in `core/urls.py` |
| 8 | P2 | `signup.html` wrong page title |

---

## 8. Dependencies

---

## 9. Post-polish update (2026-05-26)

After the final landing polish on `cursor/tf-public-landing-ae01`:

- All public nav, footer, catalog, PDP, and product card UI translated to **English**
- New assets: `tf-sections.css`, `tf-hero-animations.css`, `tf_countup.js`, `tf_hero_animations.js`, `tf_reveal.js`
- Hero stats redesigned with CountUp; ship uses `ship-cargo.svg` + `is-revealed` animation
- Sections split: `home_why_section.html`, `home_hiw_section.html`, `home_cta_section.html`
- Nav anchor updated to `#how-it-works`

See `CHANGELOG.md` for full file list.
