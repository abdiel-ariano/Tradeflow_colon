# AUDITORIA_CATALOGO_BUYER.md

**Fecha:** 2026-07-02  
**Alcance:** Vista de catálogo / tienda para compradores (autenticados e invitados) — **no** incluye `home_view` ni `templates/core/home.html`.  
**Metodología:** Trazado código (vista → contexto → templates → includes → merchandising → imágenes). Sin cambios de comportamiento en esta fase de auditoría salvo lo indicado en sección de fixes recomendados.

---

## 1. Ruta y vista

| Campo | Valor |
|-------|--------|
| **URL principal** | `/tienda/` (`name='tienda'`) |
| **Vista** | `core/views.py` → función `tienda` (línea ~3037) |
| **Decorador** | `@catalog_access` — invitados y compradores/admins autenticados |
| **Template principal** | `templates/core/tienda.html` |
| **Fragmento AJAX** | `templates/core/tienda_catalog_partial.html` (header `X-Requested-With: XMLHttpRequest` o `?partial=1`) |

### Relación con otras URLs

| URL | Vista | ¿Es esta vista? |
|-----|-------|-----------------|
| `/tienda/` | `tienda` | **Sí** — catálogo comprador con tabs y grid |
| `/catalogo/` | `catalogo_publico` | **No** — landing pública invitados (otro template) |
| `/catalogo/producto/<pk>/` | `catalogo_producto_detail` | Detalle público; enlazado desde cards pero no es el listado |

### Tabs “Modo IA \| Productos \| Fabricantes \| Mundial”

No son rutas distintas: son enlaces dentro del shell buyer que mutan query params sobre `/tienda/`:

| Tab | Enlace típico | Efecto |
|-----|---------------|--------|
| Modo IA | `{% url 'tienda' %}` | Landing buyer (`buyer_store_landing`) |
| Productos | `{% url 'tienda' %}` (activo) | Misma URL; grid de productos |
| Fabricantes | `{% url 'tienda' %}?vista=empresa` | `vista_tab=empresa` (vista por empresa, no auditada aquí en detalle) |
| Mundial | `{% url 'tienda' %}?buscar=worldwide` o `export` | Búsqueda filtrada |

**Archivos de tabs:** `templates/core/includes/buyer/buyer_navbar.html`, `templates/core/includes/buyer/buyer_hero_search.html`.

### Condición “landing buyer” vs “resultados”

`buyer_store_landing` en contexto (`views.py` ~3277):

```python
not buscar and not categoria and not empresa
and tab_catalogo in ('todos', '')
and page == 1
```

Cuando es `True`, se muestran hero, welcome zone, value strip y **“Recomendado para su negocio”** antes del sidebar + grid.

---

## 2. Templates involucrados

### Árbol principal (`tienda.html`)

```
tienda.html
├── [si buyer_store_landing]
│   ├── includes/buyer/buyer_hero_search.html
│   ├── includes/buyer/buyer_welcome_zone.html
│   ├── includes/buyer/buyer_value_strip.html
│   └── includes/buyer/buyer_recommended.html      ← “Recomendado para su negocio”
├── [si no landing]
│   └── includes/buyer/search_bar.html (compact)
├── aside.td-sidebar
│   └── form filtros (categoría, empresa, orden, búsqueda)
├── td-main
│   ├── [opcional] bp-promo-band (productos_promo / daily_deals)
│   ├── [opcional] td-promo (promo_banner CMS)
│   ├── nav.td-tabs (All | Deals | Bestsellers | Featured)
│   ├── [si show_spotlights] spotlights:
│   │   ├── Daily deals → product_card_unified × N
│   │   ├── Bestsellers in the Colón Free Zone → product_card_unified × N
│   │   └── Featured selection → product_card_unified × N
│   ├── #t-prod-section
│   │   ├── td-results-hdr (título + count)
│   │   ├── #td-product-grid → product_card_unified × paginado
│   │   └── paginación (tienda_pagination_slots)
└── extra_js: tienda_promo_carousel.js, tienda_catalog.js
```

### Shell global (no exclusivo de tienda pero visible aquí)

- `templates/core/base.html`
- `templates/core/includes/buyer/buyer_navbar.html` (3 niveles + tabs)

### CSS

- `static/css/buyer_portal.css`
- `static/css/tf-buyer-shell.css` (`.bh-recommended`, `.bh-rec-*`)
- `static/css/home_merchandising.css` (cards compartidas con home)

### Parcial AJAX

`tienda_catalog_partial.html` — solo reemplaza `#t-prod-section` (grid + paginación); **no** re-renderiza spotlights ni sección recomendada.

---

## 3. ¿Comparte tarjeta con el home?

**Sí, para el grid principal y los spotlights.**

| Zona | Componente | `is_public` |
|------|------------|-------------|
| Grid `#td-product-grid` | `core/includes/product_card_unified.html` | `False` |
| Spotlights (deals / bestsellers / featured) | `product_card_unified.html` | `False` |
| Promo carousel `bp-promo-card` | **Markup propio** en `tienda.html` (solo nombre + precio, sin imagen) | — |
| “Recomendado para su negocio” | **`product_image_placeholder.html` directo** — no usa `product_card_unified` | — |
| Welcome zone `bh-freq-card` | `product_image_placeholder.html` | — |

**Conclusión:** El grid y spotlights ya están unificados. La vitrina “Recomendado para su negocio” es un **componente visual separado** (solo imagen cuadrada, sin título/precio en DOM).

---

## 4. Sección “Recomendado para su negocio”

### Template

`templates/core/includes/buyer/buyer_recommended.html`

### Lógica de datos en template

```django
{% if featured_products %}
  {% for product in featured_products|slice:":5" %}
{% else %}
  {% for product in spotlight_destacados|default:productos_promo|slice:":5" %}
{% empty %}
  {# fallback hardcoded picsum.photos × 5 #}
{% endfor %}
```

### Qué envía `tienda()` al contexto

| Variable | ¿Presente en contexto? | Origen |
|----------|-------------------------|--------|
| `featured_products` | **No** | No se pasa nunca desde `tienda()` |
| `spotlight_destacados` | Sí (si `show_spotlights`) | `merch.featured_products(4)` |
| `productos_promo` | Siempre | `merch.daily_deals(8)` |

`show_spotlights` es `True` en la misma condición que `buyer_store_landing` (sin filtros, tab todos, página 1). Por tanto **en landing buyer sí hay productos reales**, vía rama `else` → `spotlight_destacados`.

### Diagnóstico del síntoma en captura (4 imágenes iguales, sin nombre/precio)

| Hipótesis | ¿Aplica? |
|-----------|----------|
| No recibe `Product` | **Parcialmente falsa** — recibe `Product`, pero la plantilla **no renderiza nombre ni precio** (solo `title` en `<a>` y la imagen) |
| Placeholder sin datos | **Falsa** en condiciones normales con catálogo seed |
| Bug: mismo objeto repetido | **Falsa** — el `for` itera lista distinta; PKs distintos |
| Misma imagen visual (seed categoría) | **Verdadera** — productos sin upload en misma categoría comparten `catalog-seeds/electronics.jpg` |
| Variable `featured_products` mal cableada | **Verdadera** — nombre de contexto no coincide; siempre cae en `else` |

### Diseño intencional vs roto

La sección está **conectada a datos** (`featured_products` / destacados), pero el diseño es una **vitrina solo-imagen** estilo Alibaba. Sin overlay de texto, parece “rota” aunque los `Product` existan. Los fallbacks `picsum.photos` en `{% empty %}` son deuda de diseño (no deberían verse en producción con `TRADEFLOW_USE_PICSUM_RUNTIME=False`).

---

## 5. Pipeline de imagen

### Grid y spotlights (vía `product_card_unified` → `product_image_placeholder`)

| Capa | Implementación |
|------|----------------|
| Templatetag | `core/templatetags/tf_media.py` |
| Filtro principal | `product_image_src` — upload → seed categoría → picsum (si flag) |
| Crop | `product_image_object_position` (`object-position` por PK) |
| Fallback JS | `data-hm-*` + `TFHomeMediaFallback` (`static/js/tf-media-fallback.js` en `base.html`) |
| SVG final | `images/home-product-fallback.svg` |

**Mismo pipeline que el home** para grid/spotlights.

### “Recomendado para su negocio”

Usa `product_image_placeholder.html` directamente → **mismo pipeline de imagen**, pero **sin** `product_card_unified` (sin badges, empresa, precio).

### Promo band `bp-promo-card`

**Sin imagen** — solo texto y precios en `tienda.html`.

### Diferencias vs home

| Aspecto | Home | Tienda comprador |
|---------|------|------------------|
| Componente card | `product_card_unified` | Igual en grid/spotlights |
| Merchandising dedupe imágenes | `_pick_unique_products(..., diverse_images=True)` en `build_guest_home_context` | **No aplicado** en `tienda()` spotlights ni recomendados |
| `home_product_media.html` | Usado en algunas secciones hero | **No usado** en tienda |

---

## 6. “Universal Docking Station” × 3 (lot 284 / 136 / 158)

### Origen en seed enterprise

`core/utils/enterprise_year_simulator.py`:

- Plantilla base: `('Universal Docking Station', ...)` en categoría Electronics (`PRODUCT_TEMPLATES[0]`).
- Por producto: `name = f'{base} — lot {rng.randint(100, 999)}'`.
- Cada producto pertenece a **una empresa distinta** (`company=co`), SKU único `1Y-{co.id}-{p_idx}`.

### ¿Bug de query o negocio válido?

| Criterio | Resultado |
|----------|-----------|
| ¿Mismo PK repetido? | **No** — son filas `Product` distintas |
| ¿JOIN duplicando filas? | **No evidente** — `tienda()` usa `active_products_base()` sin joins que multipliquen |
| ¿Mismo proveedor? | **No** — diseño multi-empresa del simulador |
| ¿Mismo nombre base + distinto lote? | **Sí** — comportamiento esperado marketplace B2B |

**Veredicto Paso 1:** **Comportamiento esperado de negocio**, no bug de query. La sensación de “repetido” es **visual** (misma plantilla de producto + misma categoría → mismo seed JPEG), no duplicación de registro.

### Presentación actual en card

`product_card_unified.html` **sí muestra** nombre completo (`Universal Docking Station — lot N`), empresa y precio. Si en captura solo se notan imágenes iguales, el problema es imagen/fallback, no ausencia de metadatos en el grid.

---

## 7. Hallazgos visuales / técnicos (Impeccable audit — resumen)

| ID | Severidad | Hallazgo |
|----|-----------|----------|
| CAT-01 | Alta | `buyer_recommended.html` busca `featured_products` pero `tienda()` no la envía — cableado inconsistente |
| CAT-02 | Alta | Vitrina recomendados: solo imagen, sin nombre/precio → parece sección vacía/rota |
| CAT-03 | Media | Spotlights tienda no usan `diverse_images` del merchandising (mismo fix que home bestsellers) |
| CAT-04 | Media | Fallback `picsum.photos` hardcoded en `buyer_recommended` / `buyer_welcome_zone` si listas vacías |
| CAT-05 | Baja | Promo carousel sin imagen de producto (diseño incompleto vs cards) |
| CAT-06 | Info | Multi-listing “Universal Docking Station” es válido; mejorar agrupación B2B es mejora UX, no hotfix de datos |

### Scores (dimensiones Impeccible — código medible)

| Dimensión | Score | Nota |
|-----------|-------|------|
| A11y | 2/4 | Imágenes decorativas sin `alt` consistente en vitrina; `title` en `<a>` parcial |
| Performance | 3/4 | Lazy loading en imágenes; AJAX parcial bien acotado |
| Theming | 2/4 | Mezcla tokens DS y valores hardcoded en `tienda.html` inline |
| Responsive | 3/4 | Grid y vitrina con breakpoints; touch OK en chips |
| Anti-patterns | 2/4 | Vitrina imagen-only repetida; picsum en empty states |

---

## 8. Fixes recomendados (Paso 2)

### Fix A — Imágenes repetidas en grid / spotlights

**Aplicar sin ambigüedad:**

1. En `tienda()`, envolver spotlights con `merch._pick_unique_products(..., diverse_images=True)`.
2. Pasar lista dedicada para recomendados con la misma lógica.
3. El grid paginado completo **no** debe ocultar SKUs legítimos; confiar en `object-position` + priorizar uploads en spotlights/recomendados.

### Fix B — “Recomendado para su negocio”

**Aplicar sin ambigüedad:**

1. Añadir `buyer_recommended_products` al contexto (`featured_products` con `diverse_images`).
2. Actualizar template: usar variable explícita; mostrar nombre (y opcionalmente precio) bajo imagen.
3. Si `len < 2` tras dedupe, **ocultar sección** con `{% if %}` + comentario `TODO` para recomendación personalizada futura.
4. Eliminar fallback picsum en producción.

### Fix C — Universal Docking Station

**No corregir query.** Opcional (mejora UX B2B):

- Agrupar por nombre base / SKU pattern con badge “N proveedores desde USD X”.
- Requiere diseño nuevo; fuera de hotfix mínimo.

---

## 9. Archivos clave (referencia rápida)

| Archivo | Rol |
|---------|-----|
| `core/views.py::tienda` | Vista + contexto |
| `core/merchandising.py` | `bestsellers`, `featured_products`, `daily_deals`, `_pick_unique_products` |
| `templates/core/tienda.html` | Layout principal |
| `templates/core/includes/buyer/buyer_recommended.html` | Vitrina recomendados |
| `templates/core/includes/product_card_unified.html` | Tarjeta unificada grid |
| `templates/core/includes/product_image_placeholder.html` | Pipeline imagen |
| `core/templatetags/tf_media.py` | `product_image_src`, `product_image_object_position` |
| `static/css/tf-buyer-shell.css` | Estilos vitrina `.bh-rec-*` |

---

## 10. Checklist de aceptación (post-fix)

- [ ] Ningún ícono de imagen rota en grid tienda (mismo fallback que home/carrito)
- [ ] Spotlights tienda: sin dos tarjetas adyacentes con mismo fingerprint de imagen
- [ ] “Recomendado para su negocio”: productos reales con nombre visible, o sección oculta
- [ ] Sin URLs `picsum.photos` en empty states cuando catálogo vacío
- [ ] Multi-proveedor “Universal Docking Station” sigue listándose (no agrupado salvo Fix C opcional)
