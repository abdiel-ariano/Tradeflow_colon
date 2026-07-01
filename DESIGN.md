---
name: TradeFlow Colón
description: B2B wholesale marketplace — navy authority, orange action, CFZ trust
colors:
  navy: "#0F2A44"
  navy-mid: "#1B3B63"
  navy-light: "#2E5B8A"
  orange: "#F26522"
  orange-light: "#FF7A3D"
  primary: "#0057A8"
  primary-dark: "#003D7A"
  white: "#FFFFFF"
  surface: "#F2F3F5"
  gray-700: "#343A40"
  gray-900: "#111318"
  border: "#D1D5DB"
  muted: "#6B7A88"
typography:
  display:
    fontFamily: "'DM Serif Display', Georgia, serif"
    fontSize: "clamp(1.5rem, 3vw, 2rem)"
    fontWeight: 400
    lineHeight: 1.15
  body:
    fontFamily: "'Montserrat', sans-serif"
    fontSize: "16px"
    fontWeight: 400
    lineHeight: 1.6
  ui:
    fontFamily: "'Montserrat', sans-serif"
    fontWeight: 600
rounded:
  sm: "8px"
  md: "12px"
  lg: "16px"
  pill: "999px"
spacing:
  section: "clamp(48px, 8vw, 80px)"
  card: "22px 24px"
  gap: "16px"
components:
  button-cta:
    backgroundColor: "{colors.orange}"
    textColor: "{colors.white}"
    rounded: "{rounded.sm}"
    padding: "12px 24px"
  button-outline:
    backgroundColor: "transparent"
    textColor: "{colors.white}"
    rounded: "{rounded.sm}"
    padding: "12px 24px"
  spotlight-card:
    backgroundColor: "{colors.navy}"
    textColor: "{colors.white}"
    rounded: "{rounded.lg}"
    padding: "{spacing.card}"
---

## Overview

TradeFlow's public homepage (`tf-home-v2.css`) uses a dual palette: deep navy gradients for authority, TradeFlow blue for institutional links, and orange for primary CTAs. Typography pairs DM Serif Display (section headings) with Montserrat (UI and body). Layout is section-based with mega-hero carousel, company rotator, product sliders, and category pills. Identity is committed (navy + orange borders on spotlight cards), not neutral SaaS cream.

## Colors

- **Navy stack** (`--navy`, `--navy-mid`, `--navy-light`): hero backgrounds, spotlight cards, footer.
- **Orange** (`--orange`, `--orange-light`): CTAs, badges, accent borders, rank labels.
- **Primary blue** (`--primary`, `--primary-dark`, `--primary-light`): links, secondary badges, gradient endpoints.
- **Neutrals** (`--gray-*`, `--surface`, `--border`, `--muted`): body text, cards on light sections, borders.
- Body backgrounds on marketing sections are white or navy-tinted gradients — not warm cream defaults.

## Typography

- **Display:** DM Serif Display for `.hm-section-title`, hero titles, pitch headings.
- **UI / body:** Montserrat 16px / 1.6 for `.hm-root`, buttons, cards.
- **Eyebrows:** Uppercase tracked badges (`.hm-section-badge`) — use sparingly, not on every block.
- Section titles use `clamp()`; hero titles cap around 42px on desktop compact grid.

## Elevation

- Spotlight and supplier cards: `box-shadow: 0 12px 40px rgba(15, 42, 68, 0.18)` on navy surfaces.
- Hero pitch visuals: deeper shadow `0 16px 40px rgba(0,0,0,0.3)`.
- Sliders and nav: flat; depth comes from color blocks, not floating glass panels.

## Components

- **`.hm-btn--cta`:** Orange fill, white text, 8px radius.
- **`.hm-btn--outline`:** Transparent on dark hero, bordered white/orange variants.
- **`.hm-spotlight-unified`:** Navy gradient card, 2px orange border, inner product slider on dark tint.
- **`.hm-company-rotator`:** Tab pills + absolute panels; track height synced via JS.
- **`.hm-slider`:** Transform-based horizontal sliders with prev/next arrows and dot nav.
- **Product cards (`.hm-sp-card`, `.hm-trend-card`):** White media area, title below image (not on image).

## Do's and Don'ts

**Do**
- Keep product titles below images on home cards.
- Use `aria-label` / `aria-labelledby` on carousels and sections.
- Reserve orange for primary actions and verification accents.
- Center constrained content blocks (e.g. How it Works ~1100px).

**Don't**
- Leave carousel regions silently empty — use skeleton, products, or explicit empty message.
- Use thick single-side border accents on cards (AI side-tab tell).
- Animate `min-height` for layout (prefer JS height sync without transition, or transform-based motion).
- Stack duplicate company descriptions when `tagline_es` is absent.
