# Design QA — Demo admin navigation

## Evidence

- Source visual truth:
  - `/workspace/scratch/a6bcf941a88e/upload/906b6222-1ef1-4ec8-97ab-c627fd8c552b.png`
  - `/workspace/scratch/a6bcf941a88e/upload/4072636f-c330-4434-9492-f1d55bc6a156.png`
- Source dimensions: 1916 × 913 px and 1914 × 930 px.
- Implementation URL:
  `https://tradeflow-colon-git-fix-demo-2bff41-tradeflow-colon-s-projects.vercel.app`
- Implementation screenshot: unavailable because Vercel Deployment Protection
  redirects the cloud browser to the Vercel login screen.
- Browser viewport: managed Chrome desktop viewport.
- CSS size and density normalization: not available without the authenticated
  implementation capture.
- State: authenticated `demo_admin` on the metrics dashboard and SaaS panel.

## Full-view comparison

Blocked. The source screenshots were opened and inspected. The deployed preview
was also opened, but Vercel Deployment Protection prevented the admin screen
from rendering in the verification browser. A valid side-by-side visual
comparison therefore could not be produced.

## Focused region comparison

Blocked for the same reason. The intended region is the complete left navigation
rail, especially Inventory, Payments, Quotes, Users, Shipments, Carriers,
Subscriptions, Email audit, and API audit.

## Code-level corrections verified

- All 15 custom-rail destinations use the `adm-rail-link` component class.
- The source stylesheet and embedded CSS bundle target the same class.
- Link underlines and inherited browser colors are overridden explicitly.
- The read-only banner, dataset, JavaScript button lock, middleware redirect,
  and SaaS API write rejection were removed.
- Each module keeps its own Django Admin URL.
- Automated tests and Vercel build checks pass on the pull-request head.

## Primary interactions tested

- Automated Django tests cover direct `/admin/` access, staff restoration,
  full model permissions, absence of the read-only banner, all 15 rail items,
  and writable SaaS action dispatch.
- Browser click-through testing could not run because the preview is protected.

## Console errors checked

Not checked. The protected preview never loaded the TradeFlow application.

## Findings

- [P1] Visual verification is blocked by preview authentication.
  - Location: Vercel preview deployment.
  - Evidence: the preview redirects to `vercel.com/login` before TradeFlow
    renders.
  - Impact: responsive styling and click-through behavior cannot be confirmed
    visually in the cloud browser.
  - Fix: open the preview from an authorized Vercel session or merge and verify
    the same routes on the production deployment.

## Comparison history

1. Initial source inspection identified browser-default blue underlined links
   and a read-only banner.
2. Code fixes standardized the rail component and removed read-only gates.
3. Post-fix screenshot comparison remains unavailable because deployment
   protection blocks the implementation capture.

## Implementation checklist

- [x] Remove read-only middleware redirection.
- [x] Enable persistent demonstration-admin access.
- [x] Standardize every custom-rail destination.
- [x] Synchronize embedded and source CSS.
- [x] Add automated regression coverage.
- [ ] Capture the authenticated preview at the same desktop viewport.
- [ ] Click Inventory, Payments, Users, Shipments, and API audit in-browser.
- [ ] Compare the rendered rail with the supplied screenshots.

## Final result

final result: blocked
