# Design System

**Purpose:** Visual language, components, and interaction principles for Nexarch's UI. This document is written ahead of any UI code being built, per the founding process — treat it as the brief a designer would hand to an engineer, not as a retrospective description of existing screens. See [development-guide.md](./development-guide.md) for how this maps to actual Tailwind config once implementation starts.

---

## Philosophy

Dark mode first. Minimal. Premium. The reference points named at founding — Linear, Stripe, Apple, Notion — share a common thread worth naming explicitly rather than just imitating surface style: **restraint.** Few colors used deliberately, generous whitespace, typography doing most of the work, and motion that clarifies state changes rather than decorating them. The instruction to avoid copying any existing fintech UI is worth taking seriously — most Indian fintech apps default to bright, busy, gamified interfaces (badges, streaks, confetti). Nexarch's entire premise is trust over hype, and the UI should feel like that premise even before a user reads any copy.

## Color

A dark, near-neutral base rather than pure black, with one deliberate accent — avoiding the common "growth green" that most Indian trading apps already use as their primary brand color, so Nexarch doesn't visually blend into the category it's trying to differentiate from:

| Token | Use | Value (proposed) |
|---|---|---|
| `--bg-primary` | App background | `#0B0B0E` |
| `--bg-surface` | Cards, elevated panels | `#15151B` |
| `--bg-surface-hover` | Hover state on surfaces | `#1D1D24` |
| `--text-primary` | Primary text | `#F5F5F7` |
| `--text-secondary` | Secondary/muted text | `#9A9AA5` |
| `--accent` | Primary brand accent | `#6C6CF2` (indigo) |
| `--accent-hover` | Accent hover/active | `#8484F5` |
| `--positive` | Gains, up movement | `#3DD68C` |
| `--negative` | Losses, down movement | `#F2555A` |
| `--border` | Dividers, card borders | `#242430` |

The `--positive`/`--negative` convention (green up, red down) stays even though the overall palette avoids green-as-brand — this is a strong, near-universal financial-data convention and deviating from it purely for differentiation would hurt usability for no real benefit.

## Typography

- **UI/body:** Inter (or a similar modern grotesque) — legible at small sizes, wide language support.
- **Numeric/tabular data:** a font with proper tabular figures (Inter's tabular-nums feature, or a monospace like JetBrains Mono for dense holdings tables) so numbers align in columns instead of jittering as digits change width.
- **Scale:** a standard modular scale (12/14/16/20/24/32/40px) rather than inventing bespoke sizes per screen.

## Spacing

4px base unit, following Tailwind's default spacing scale (`1` = 4px, `2` = 8px, `4` = 16px, etc.) rather than a custom scale — one less thing to maintain, and the default scale is well-proven.

## Core Components

| Component | Notes |
|---|---|
| `Button` | Primary (accent-filled), secondary (outline), ghost (text-only) |
| `Card` | The base surface for portfolio blocks, discovery-feed items |
| `Badge` | Verification badge, strategy tags — small, subtle, never loud (a badge shouldn't look like a gamification reward) |
| `HoldingsTable` | Tabular-nums, sortable, sticky header on scroll |
| `AllocationChart` | Recharts-based donut/bar for sector and asset allocation |
| `StatCard` | A single metric with label — used for portfolio-health indicators, deliberately not styled as a "score" (see [product-requirements.md](./product-requirements.md) on why there's no single trust score) |
| `Avatar` | User/public-investor profile image with graceful fallback (initials) |
| `Modal` | Confirold dialogs (broker disconnect, make-private) |
| `EmptyState` | Needed early — a fresh account with no synced portfolio yet is a common state, not an edge case |

## Responsive Behavior

Tailwind's default breakpoints (`sm`/`md`/`lg`/`xl`/`2xl`). Discovery feed and portfolio pages should be designed mobile-first — the founding brief doesn't specify a native app, but a large share of Indian retail-investing usage is mobile web/app, and a desktop-first design that's "made responsive" afterward tends to show it.

## Accessibility

- Dark-mode contrast ratios checked against WCAG AA at minimum for all text/background pairs above (the palette above needs a contrast pass once implemented, not just assumed correct because it "looks fine").
- All interactive elements keyboard-navigable with visible focus states — easy to lose in a dark, minimal palette if not checked deliberately.
- Charts (allocation donuts, history graphs) need a text-equivalent summary for screen readers (e.g., a visually-hidden data table alongside the chart), since a chart alone communicates nothing to a non-visual user.
- Semantic HTML and ARIA labels throughout — a trust-focused product loses credibility fast if it's inaccessible to some of the people evaluating that trust.

## Animation

Framer Motion, used for clarity, not decoration:
- Skeleton loaders during data fetch (portfolio sync can take a moment)
- Subtle count-up animation for headline portfolio stats on load
- Page-transition and modal-entry motion kept short (150–250ms) — premium reads as fast and quiet, not as elaborate.

## Data Visualization Conventions

- Consistent color mapping per sector across every chart on the platform (a sector should always render in the same color wherever it appears, so users build pattern recognition across profiles).
- Consistent green-up/red-down for any performance figure, per the color table above.
- Every chart ships with the accessible text-equivalent described above from day one, not retrofitted later.
