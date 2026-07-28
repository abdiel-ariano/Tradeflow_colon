# Design QA — Admin language, typography, and navigation

## Evidence

- Source issue captures:
  - `/workspace/scratch/a6bcf941a88e/upload/c9b8a8b6-0298-4877-a2a1-dad0a06b6f18.png`
  - `/workspace/scratch/a6bcf941a88e/upload/998e5594-4ba9-43b2-8984-9f6ecfc624cb.png`
- Source dimensions: 1917 × 923 px and 1903 × 903 px.
- Implementation: pull request #435 deployment.
- Implementation screenshot: unavailable because Vercel Deployment Protection
  requires an authenticated session before TradeFlow renders.
- Browser viewport: managed Chrome desktop viewport.
- States: Payments changelist and CFZ sales dashboard.

## Full-view comparison

Blocked for post-fix evidence. The supplied captures were opened and compared.
They show the same product using mixed Spanish/English navigation, Montserrat
page headings in Django Admin versus the established DM Serif Display dashboard
heading, and a long ungrouped rail that requires scrolling.

## Focused region comparison

Blocked. The focused targets are the main page title, header actions, section
labels, active navigation item, and accordion open/closed states.

## Required fidelity surfaces

- Fonts and typography: Montserrat is assigned to interface copy and controls;
  DM Serif Display is assigned to primary page headings.
- Spacing and layout rhythm: section labels become compact accordion summaries,
  with only one expanded group and the active group opened automatically.
- Colors and visual tokens: existing navy, orange, white, and muted-blue tokens
  are preserved for summary, hover, active, and open states.
- Image quality and asset fidelity: existing TradeFlow logo and Material Symbols
  are reused; no assets are replaced.
- Copy and content: custom administrative shell labels are consistently English,
  matching the established dashboard and Django locale. Business data remains
  unchanged.

## Code-level corrections verified

- DM Serif Display is added to the existing font request.
- A documented CSS contract separates display and interface typography.
- Both sidebar templates use English category and action labels.
- One shared script highlights the active route and builds accessible details
  groups for both administrative shells.
- The active group opens first; opening a group closes its siblings.
- Session storage preserves the operator's last selected category.
- Automated tests cover language, font assets, script presence, and route-aware
  accordion selectors.

## Primary interactions tested

- Automated coverage opens the Payments changelist and custom dashboard.
- Browser click-through cannot reach the protected preview.

## Console errors checked

Not checked because the protected deployment does not render TradeFlow.

## Findings

- [P1] Post-fix visual and interaction verification is blocked.
  - Location: Vercel preview for pull request #435.
  - Evidence: the preview redirects unauthenticated traffic to Vercel login.
  - Impact: final font rendering and accordion toggling cannot be captured from
    the verification browser.
  - Fix: inspect the authorized preview or verify after merge.

## Comparison history

1. Previous iterations unified the admin shell and viewport layout.
2. The new captures revealed mixed language, mismatched display typography, and
   excessive navigation scrolling.
3. The current implementation applies the established font contract, English
   labels, and shared route-aware accordion navigation.
4. Post-fix browser evidence remains blocked by the private preview.

## Implementation checklist

- [x] Use Montserrat for interface typography.
- [x] Use DM Serif Display for primary page titles.
- [x] Standardize administrative labels in English.
- [x] Group both sidebars into accessible accordions.
- [x] Open the active route group automatically.
- [x] Preserve the selected group during the session.
- [x] Add automated regression coverage.
- [ ] Capture the authenticated preview.
- [ ] Test every accordion group and browser console visually.

## Final result

final result: blocked
