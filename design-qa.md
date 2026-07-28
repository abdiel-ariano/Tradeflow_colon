# Design QA — Full-width Django Admin shell

## Evidence

- Source issue captures:
  - `/workspace/scratch/a6bcf941a88e/upload/8c350a60-7169-466e-97c6-1abf8c16e874.png`
  - `/workspace/scratch/a6bcf941a88e/upload/4c6e3760-8763-4e10-a93b-59bf30ef9c8a.png`
  - `/workspace/scratch/a6bcf941a88e/upload/8a453d60-09b8-4ba5-9c82-003a432541e0.png`
- Source dimensions: 1915 × 923 px, 1914 × 930 px, and 1913 × 920 px.
- Intended visual baseline:
  - `/workspace/scratch/a6bcf941a88e/upload/906b6222-1ef1-4ec8-97ab-c627fd8c552b.png`
  - `/workspace/scratch/a6bcf941a88e/upload/4072636f-c330-4434-9492-f1d55bc6a156.png`
- Implementation: pull request #433 deployment.
- Implementation screenshot: unavailable because Vercel Deployment Protection
  requires an authenticated Vercel session before TradeFlow renders.
- Browser viewport: managed Chrome desktop viewport.
- State: administration index, Payments changelist, and Quotes changelist.

## Full-view comparison

Blocked. The supplied issue captures were opened and inspected. They show the
administration index restricted to a narrow centered column, changelists using
only part of the available canvas, and Django's native user toolbar replacing
the TradeFlow header. The protected preview cannot be captured after the fix.

## Focused region comparison

Blocked for the same reason. The required focused regions are the persistent
header, the 252 px navigation rail, the changelist data area, the 272 px filter
column, and the full-width administration index.

## Required fidelity surfaces

- Fonts and typography: Montserrat remains the shared body, control, and header
  family; the replacement user toolbar no longer inherits Django's uppercase
  native presentation.
- Spacing and layout rhythm: content and dashboard width restrictions are
  removed; changelists use an explicit flexible-data/fixed-filter grid.
- Colors and visual tokens: the existing navy, orange, white, and light-gray
  TradeFlow tokens remain unchanged.
- Image quality and asset fidelity: the existing TradeFlow logo and Material
  Symbols are reused without replacement or approximation.
- Copy and content: administrative records and filters remain intact; the header
  actions are clarified as Marketplace, Seguridad, and Salir.

## Code-level corrections verified

- A Django 6-compatible base template keeps one header across admin routes.
- `#content`, `#content-main`, and the dashboard can use the full canvas.
- Changelists allocate the remaining width to data and 272 px to filters.
- Tables scroll internally only when their columns exceed the available width.
- Filters move below the table on narrower desktop and tablet layouts.
- Dedicated regression tests cover the shared header and final layout layer.

## Primary interactions tested

- Automated coverage requests the Payments changelist and administration index.
- Browser click-through remains blocked by Vercel Deployment Protection.

## Console errors checked

Not checked because the protected preview never rendered TradeFlow.

## Findings

- [P1] Post-fix browser verification is blocked by preview authentication.
  - Location: Vercel preview deployment for pull request #433.
  - Evidence: Vercel redirects unauthenticated preview traffic to its login.
  - Impact: final rendered widths, wrapping, and responsive transitions cannot
    be compared in-browser from this environment.
  - Fix: inspect the authorized preview or merge and verify the same routes in
    production.

## Comparison history

1. The first implementation normalized color, font loading, and table surfaces.
2. New captures revealed remaining inherited width constraints and a native
   Django header that caused abrupt transitions.
3. The second implementation introduced a shared base header, full-width canvas,
   explicit changelist grid, and responsive filter placement.
4. Post-fix browser evidence remains unavailable because the preview is private.

## Implementation checklist

- [x] Keep one TradeFlow header across native admin routes.
- [x] Remove inherited dashboard and content width restrictions.
- [x] Give changelist data all remaining horizontal space.
- [x] Keep filters in a stable 272 px desktop column.
- [x] Preserve internal overflow for genuinely wide tables.
- [x] Add responsive filter stacking.
- [x] Add automated regression coverage.
- [ ] Capture the authorized PR preview at the supplied viewport.
- [ ] Verify Payments, Quotes, Products, and Inventory visually.
- [ ] Check the browser console on the authenticated implementation.

## Final result

final result: blocked
