# Design QA — Viewport-wide Django Admin

## Evidence

- Source issue captures:
  - `/workspace/scratch/a6bcf941a88e/upload/4f124b07-e429-4a43-9720-0d1871a9d40c.png`
  - `/workspace/scratch/a6bcf941a88e/upload/ccc9bd8c-0e86-4423-a33e-cd33a6b83350.png`
  - `/workspace/scratch/a6bcf941a88e/upload/18049126-b1d9-4bf8-8831-829eee14e6d8.png`
  - `/workspace/scratch/a6bcf941a88e/upload/60d8a70e-ad7f-49a6-ae77-dba7325205bc.png`
- Source dimensions: 1910 × 921 px, 1910 × 926 px, 1906 × 902 px, and
  1904 × 921 px.
- Implementation: pull request #434 deployment.
- Implementation screenshot: unavailable because Vercel Deployment Protection
  requires an authenticated Vercel session before TradeFlow renders.
- Browser viewport: managed Chrome desktop viewport.
- States: logistics events, transport carriers, orders, and administration index.

## Full-view comparison

Blocked. The supplied captures were opened and inspected. They show that the
TradeFlow header is present, but changelist data remains constrained because
Django 6 limits the direct child of `.changelist-form-container`. The prior
selector targeted the outer `#changelist` and therefore could not remove the
actual 270 px reservation.

## Focused region comparison

Blocked for post-fix evidence. The required regions are the fixed top header,
the direct changelist container, the result table, filters, and the full-width
administration module grid.

## Required fidelity surfaces

- Fonts and typography: unchanged Montserrat hierarchy.
- Spacing and layout rhythm: the inner Django flex container is replaced by an
  explicit grid; data receives all remaining width and filters receive 272 px.
- Colors and visual tokens: existing TradeFlow navy, orange, white, and gray.
- Image quality and asset fidelity: original logo and Material Symbols retained.
- Copy and content: records, actions, filters, and labels remain unchanged.

## Code-level corrections verified

- The header uses fixed viewport positioning and a compensated document offset.
- Main content is calculated against the viewport and persistent rail.
- `.changelist-form-container` overrides Django's internal flex and max-width.
- Result tables use the complete width and wrap cells instead of creating an
  inner horizontal scroll region.
- Filters stack beneath data below the desktop breakpoint.
- Dashboard modules can use three columns on large monitors.
- Regression assertions cover fixed positioning, the Django 6 `:has()` target,
  and removal of the nested horizontal scroll.

## Primary interactions tested

- Automated Django coverage requests the Payments changelist and admin index.
- Browser interaction remains blocked by Vercel Deployment Protection.

## Console errors checked

Not checked because the protected preview does not render TradeFlow.

## Findings

- [P1] Post-fix browser verification is blocked by preview authentication.
  - Location: Vercel preview for pull request #434.
  - Evidence: unauthenticated preview requests redirect to Vercel login.
  - Impact: the final widths and fixed-header scroll behavior cannot be observed
    from the verification browser.
  - Fix: inspect the authorized preview or verify the same routes after merge.

## Comparison history

1. Initial styling normalized typography and light theme surfaces.
2. A shared header and outer full-width shell were introduced.
3. New captures proved that Django 6's inner flex container still constrained
   data and that sticky positioning was insufficient for every scroll state.
4. The current fix targets that inner container and fixes the header to the
   viewport.
5. Post-fix browser evidence remains blocked by the private preview.

## Implementation checklist

- [x] Fix the top header to the viewport.
- [x] Compensate document flow for the fixed header.
- [x] Override the actual Django 6 inner layout container.
- [x] Remove the inherited 270 px data restriction.
- [x] Use all remaining viewport width.
- [x] Remove the nested horizontal result scroller.
- [x] Wrap wide cells within the full-width table.
- [x] Add regression assertions.
- [ ] Capture and compare the authenticated PR preview.
- [ ] Check the console on an authenticated screen.

## Final result

final result: blocked
