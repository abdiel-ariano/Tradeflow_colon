# Design QA — Native Django Admin consistency

## Evidence

- Source visual truth:
  - `/workspace/scratch/a6bcf941a88e/upload/3cbf7688-e2f5-44e8-b24a-f4c81cff6d22.png`
  - `/workspace/scratch/a6bcf941a88e/upload/d72bf69e-f330-4d0d-8dab-3edd7c9af561.png`
- Source dimensions: 1888 × 922 px and 1892 × 912 px.
- Intended visual baseline:
  - `/workspace/scratch/a6bcf941a88e/upload/906b6222-1ef1-4ec8-97ab-c627fd8c552b.png`
  - `/workspace/scratch/a6bcf941a88e/upload/4072636f-c330-4434-9492-f1d55bc6a156.png`
- Implementation URL:
  `https://tradeflow-colon-git-fix-admin-406d89-tradeflow-colon-s-projects.vercel.app`
- Implementation screenshot: unavailable because Vercel Deployment Protection
  redirects the cloud browser to the Vercel login screen.
- Browser viewport: managed Chrome desktop viewport.
- CSS size and density normalization: unavailable without the authenticated
  implementation capture.
- State: authenticated administration index and Inventory changelist.

## Full-view comparison

Blocked. Both supplied Django Admin screenshots and the original TradeFlow admin
baseline were opened and inspected. The pull-request deployment was opened in a
cloud browser, but Vercel Deployment Protection redirected it to the Vercel
login page before TradeFlow rendered. A post-fix screenshot comparison cannot
be produced from the protected preview.

## Focused region comparison

Blocked for the same reason. The required focused regions are the 252 px left
navigation rail, header typography, changelist search and actions toolbar,
table header, alternating rows, and horizontally scrollable results region.

## Required fidelity surfaces

- Fonts and typography: the native admin now loads Montserrat and applies it to
  body copy, headings, controls, buttons, tables, breadcrumbs, and messages.
- Spacing and layout rhythm: the persistent rail is normalized to 252 px and
  native admin content offsets share the same rail-width token.
- Colors and visual tokens: light Django variables are explicitly defined for
  light, dark, and automatic browser preferences, preventing black native
  toolbars and rows from overriding TradeFlow tokens.
- Image quality and asset fidelity: the existing TradeFlow logos and Material
  Symbols remain unchanged; no image assets were replaced.
- Copy and content: Django labels, records, actions, and app-specific content
  are preserved without introducing presentation-only placeholder copy.

## Code-level corrections verified

- The native compatibility stylesheet loads after the original admin theme.
- Dark and automatic theme selectors resolve to the same TradeFlow light tokens.
- Search, actions, filters, forms, messages, object tools, and result rows use a
  coherent light treatment.
- Wide changelists scroll within the results container instead of cropping the
  entire page.
- Responsive rules collapse the persistent rail below the desktop breakpoint.
- An automated regression test verifies the stylesheet, font import, rail token,
  theme override, and row treatment.
- GitHub Actions and the Vercel deployment check pass on the pull-request head.

## Primary interactions tested

- Automated Django coverage opens the Inventory changelist and verifies that the
  native compatibility layer is present and resolvable through staticfiles.
- Browser interaction testing could not reach the authenticated TradeFlow screen
  because the preview is protected.

## Console errors checked

Not checked. The protected preview never loaded the TradeFlow application.

## Findings

- [P1] Post-fix visual verification is blocked by preview authentication.
  - Location: Vercel preview deployment.
  - Evidence: the preview redirects to `vercel.com/login` before TradeFlow
    renders.
  - Impact: final font rendering, responsive behavior, and changelist overflow
    cannot be visually confirmed in the deployed environment.
  - Fix: verify the preview from an authorized Vercel session or merge and test
    the Inventory, Products, Users, and Orders routes in production.

## Comparison history

1. Source inspection found an abrupt font change, oversized rail, black search
   toolbar, black alternating rows, and cropped wide changelists.
2. The implementation added a documented native-admin compatibility layer,
   Montserrat loading, stable light tokens, a 252 px rail, and internal table
   overflow handling.
3. Automated CI and deployment checks passed.
4. Post-fix browser capture remains unavailable because deployment protection
   blocks the implementation screen.

## Implementation checklist

- [x] Load Montserrat in native Django Admin.
- [x] Stabilize light tokens across browser theme preferences.
- [x] Match the original 252 px TradeFlow navigation rail.
- [x] Normalize changelists, forms, filters, actions, and messages.
- [x] Keep wide tables inside a horizontal results scroller.
- [x] Add automated regression coverage.
- [x] Pass GitHub Actions and Vercel deployment checks.
- [ ] Capture Inventory and Products at the supplied desktop viewport.
- [ ] Verify the collapsed navigation at responsive breakpoints.
- [ ] Check the browser console on an authenticated application screen.

## Final result

final result: blocked
