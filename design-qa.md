# Design QA — Shared TradeFlow administration shell

## Evidence

- Reference capture, sales dashboard:
  `3a40a1de-4946-4745-92ec-91881ab2beb0.png`.
- Reference capture, Django Admin carrier list:
  `5c669dc9-dd0b-49e4-a6dd-ab67a684b2bc.png`.
- Source dimensions: 1919 × 920 px and 1919 × 902 px.
- Implementation: draft pull request #436.
- Preview:
  `tradeflow-colon-git-agent-uni-5709df-tradeflow-colon-s-projects.vercel.app`.
- Browser-rendered implementation screenshot: unavailable.
- CSS viewport and device scale factor: unavailable because the managed browser
  did not receive permission to open the preview.
- Target states: CFZ sales dashboard and native Django Admin changelists.

## Target fidelity

Moving between the dashboard and any Django Admin module must preserve:

- the compact 64 px top navigation;
- the same TradeFlow icon, operator name, and Sign out action;
- the same 252 px accordion rail and active-route treatment;
- Montserrat typography for headings, controls, tables, and navigation;
- the same language and capitalization;
- a full-width content canvas without nested horizontal scrolling.

## Code-level comparison completed

- Both surfaces include `templates/core/admin_rail.html`.
- Both surfaces load `static/css/tradeflow_admin_continuity.css` last.
- Django Admin and the dashboard use the same compact user header contract.
- The legacy DM Serif heading rules were removed from the administrative shell.
- The route-aware script opens the active accordion group and preserves the
  selected group for the browser session.
- Native changelists use the remaining viewport width and wrap table content.
- Regression tests cover the shared rail, header, typography, and full canvas.

## Browser comparison

Blocked. The managed browser request to open the Vercel preview was declined,
so a post-fix screenshot, equal-viewport composite, and focused comparison
cannot be produced. No retry or alternate browser was attempted.

## Primary interactions tested

- Automated Django coverage requests the sales dashboard, the admin index, and
  native changelists.
- Static JavaScript syntax validation passed.
- Browser click-through between rail groups remains unverified.

## Console errors checked

Not checked because the preview could not be opened in the managed browser.

## Findings

- [P1] Post-fix visual parity remains unverified in a real browser.
  - Location: pull request #436 preview.
  - Impact: the final rendered header height, font loading, accordion behavior,
    and table width cannot yet be compared pixel-for-pixel.
  - Resolution: open the authorized preview and repeat full-view and focused
    comparisons at the same viewport as the reference captures.

## Comparison history

1. The references show two independent shells with different logos, user
   controls, typography, menu structure, capitalization, and spacing.
2. Pull request #436 replaces those duplicate structures with one shared rail,
   one compact header contract, and one final continuity stylesheet.
3. Automated and code-level validation covers the required invariants.
4. Browser evidence is still required before this design gate can pass.

## Implementation checklist

- [x] One navigation partial for dashboard and Django Admin.
- [x] One compact header contract.
- [x] Montserrat throughout the administrative interface.
- [x] English labels and consistent capitalization.
- [x] Route-aware accordion categories.
- [x] Full-width native admin content.
- [x] Automated regression coverage.
- [ ] Authenticated browser screenshot at the reference viewport.
- [ ] Full-view and focused visual comparison.
- [ ] Browser interaction and console verification.

## Final result

final result: blocked
