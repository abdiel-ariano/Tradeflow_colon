# Product

> **Resumen en español:** TradeFlow Colón es el marketplace mayorista B2B de la Zona
> Libre de Colón. Compradores de las Américas descubren proveedores verificados,
> comparan MOQ en USD y solicitan cotizaciones con documentación de exportación.
> Vendedores gestionan catálogo y planes SaaS; operadores administran la plataforma.
> Documentación técnica: [docs/DOCUMENTACION_TECNICA.md](docs/DOCUMENTACION_TECNICA.md).

## Register

product

## Users

- **Buyers (primary on public surfaces):** Wholesale purchasers, importers, and retail chains sourcing from the Colón Free Zone. They browse catalogs without an account, compare verified suppliers, and convert when ready to place B2B orders.
- **Sellers:** CFZ-based distributors and manufacturers managing catalogs, visibility plans, and fulfillment through TradeFlow.
- **Operators:** Internal admins overseeing companies, merchandising, and platform health.

Public landing visitors are often first-time buyers evaluating trust, catalog depth, and export readiness before signup.

## Product Purpose

TradeFlow Colón is a B2B wholesale marketplace connecting buyers across the Americas with CFZ-verified suppliers. Success means buyers find credible inventory fast, understand how the platform works, and reach checkout or quote flows with confidence; sellers gain qualified visibility; the platform communicates institutional trust (Free Zone, documentation, verification).

## Brand Personality

**Confident · Verified · Pan-American**

Voice is professional and export-ready, not startup-hype. Emphasize verification, scale (SKUs, companies, countries), and operational seriousness. Orange signals action; navy signals authority. Avoid casual consumer-marketplace tone.

## Anti-references

- Generic AI SaaS landing (cream body, purple gradients, hero metric grid, identical icon cards).
- Consumer e-commerce (flash sales, cart-first, playful illustrations).
- Overly dense enterprise dashboards on the public homepage.
- Unverified marketplace aesthetics (no trust signals, anonymous suppliers).
- Side-accent card stripes and gradient text as decorative filler.

## Design Principles

1. **Trust before transaction** — Verification badges, stats, and supplier credentials appear before aggressive CTAs.
2. **Show real inventory** — Product imagery and company spotlights use live catalog data, never silent empty regions.
3. **One marketplace, two registers** — Public landing is brand-forward; app surfaces are task-forward. Do not import dashboard density into the homepage.
4. **Export-ready clarity** — Copy and hierarchy answer: who sells, what's available, how to order, what documentation is included.
5. **Motion with purpose** — Carousels and reveals aid discovery; respect `prefers-reduced-motion`.

## Accessibility & Inclusion

- Target **WCAG 2.1 AA** for public pages.
- Maintain visible focus states on carousel controls and nav pills.
- Decorative product images on home use empty `alt` where titles are adjacent; meaningful images retain descriptive alt.
- Honor `prefers-reduced-motion` (already implemented on `.hm-root`).
- Touch targets ≥44px on mobile carousel arrows and company tabs.
