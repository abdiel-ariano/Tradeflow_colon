# CHANGELOG — Public Landing Polish

**Branch:** `cursor/tf-public-landing-ae01`  
**Date:** 2026-05-26

## Summary

Final polish of the TradeFlow Colón public landing: full English UI, redesigned hero stats, animated ship + waves, and new section layouts with scroll reveal animations.

## Added

| File | Purpose |
|------|---------|
| `DIAGNOSIS.md` | Baseline audit of public shell before polish |
| `static/css/tf-sections.css` | Hero stats, Why, Companies, How it works, CTA, reveal animations |
| `static/css/tf-hero-animations.css` | Ship entrance + SVG wave layers |
| `static/js/tf_countup.js` | CountUp for hero stat numbers |
| `static/js/tf_hero_animations.js` | IntersectionObserver ship reveal |
| `static/js/tf_reveal.js` | Global `[data-reveal]` scroll animations |
| `templates/core/includes/home_why_section.html` | Why TradeFlow grid |
| `templates/core/includes/home_hiw_section.html` | How it works timeline |
| `templates/core/includes/home_cta_section.html` | Dual buyer/seller CTA |

## Changed

- **`templates/core/home.html`** — loads new CSS/JS; section includes reordered
- **`templates/core/includes/hero_section.html`** — new stats cards + ship/waves markup
- **`templates/core/includes/home_companies_section.html`** — redesigned company cards
- **`templates/core/includes/public_navbar.html`** — full English nav
- **`templates/core/includes/tf_header_search.html`** — English labels/placeholder
- **`templates/core/base.html`** — English footer
- **`templates/core/catalogo_publico.html`** — full English catalog UI
- **`templates/core/includes/catalogo_publico_results.html`** — English empty/pagination
- **`templates/core/catalogo_producto_detail.html`** — English PDP + catalog links
- **`templates/core/includes/product_card_unified.html`** — English CTA + public catalog links
- **`templates/core/signup.html`** — fixed page title
- **`templates/core/includes/home_grid.html`** — category links → `catalogo_publico`
- **`core/views.py`** — `titulo_pagina` → `Catalog`
- **`core/tests/test_catalogo_publico.py`** — assertions updated for English strings
- **`static/css/tf-header.css`** — category menu utility classes

## Removed / Deprecated

- Inline count-up and ship JS from `home.html` (moved to dedicated files)
- `home_features_section.html` no longer included (split into why/hiw/cta)
- `tf-hero-ship.css` no longer loaded (replaced by `tf-hero-animations.css`)

## Notes

- Ship asset: `static/img/ship-cargo.svg` (SVG, not PNG)
- Anchor `#how-it-works` replaces `#como-funciona` in nav/footer
- `prefers-reduced-motion` respected in all new animations
- Company model has no `logo` field — avatars use gradient initials via `{% cycle %}`
