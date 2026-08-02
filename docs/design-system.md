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
- A two-portfolio comparison's per-metric delta (Milestone 6) is shown neutrally — no green/red judgment coloring. Unlike a rising/falling value over time, "higher" isn't consistently good or bad across these metrics (a higher concentration/HHI is more concentrated, not "worse" in a way this product ranks — see ADR-007 in [decisions.md](./decisions.md)); the green-up/red-down convention above is reserved for genuinely directional performance figures, not for which side of a comparison happens to be numerically larger.

---

## Implementation status (2026-07-31)

The sections above are the original brief, written before any UI existed. This
section records what was actually built, where it diverges, and why.

### Composition primitives

Pages are composed from these and nothing else. Before them every route
hand-rolled its own shell (`max-w-5xl px-4 py-10` here, `max-w-3xl` there,
`min-h-screen justify-center` on the landing page), so no two pages shared a
column width or vertical rhythm.

| Primitive | File | Role |
|---|---|---|
| `PageContainer` | `components/ui/Layout.tsx` | Column width, gutter, rhythm, `#main` skip target. Renders `<main>` |
| `ContentWidth` | `components/ui/Layout.tsx` | The column *without* `<main>`, for full-bleed pages whose bands need edge-to-edge rules |
| `PageHeader` | `components/ui/Layout.tsx` | Page title (40px), description, actions, eyebrow |
| `PageSection` | `components/ui/Layout.tsx` | Titled band; owns the space above itself |
| `SectionTitle` | `components/ui/Layout.tsx` | Section heading (24px) + hairline rule |
| `SectionDivider` | `components/ui/Layout.tsx` | Sub-section rule, `aria-hidden` |
| `Surface` | `components/ui/Surface.tsx` | The single source of the card look; tones `default`/`raised`/`quiet` |
| `DataCard` | `components/ui/Surface.tsx` | Titled panel (`<h3>`) for a chart or table |
| `InfoRow` / `InfoList` | `components/ui/Surface.tsx` | Label/value pairs as a real `<dl>` |
| `Metric` | `components/ui/Metric.tsx` | Every number in the product |
| `Eyebrow` | `components/ui/Metric.tsx` | Mono uppercase label above a metric |
| `StatCard` | `components/ui/Metric.tsx` | One labelled health indicator, never a score |
| `AuthLayout` / `Field` | `components/ui/AuthLayout.tsx` | The shell + labelled field for login, register, broker callback |
| `Skeleton` + presets | `components/ui/Skeleton.tsx` | Loading placeholders shaped like their content |
| `PortfolioIdentityStrip` | `components/ui/PortfolioIdentityStrip.tsx` | The signature element — see below |

Deleted as duplicates: `Card`, `Figure`, `Section`, `StatCard` (standalone),
`PortfolioFingerprint`. Every page now composes from the primitives above —
no page defines its own shell, card, heading or metric styling.

### Type scale

Roles, not sizes, so a heading can't drift to a bespoke value per screen.
Hero 52 · Page title 40 · Section title 24 · Card title 20 · Body 16 ·
Meta 14 · Caption 12. Page titles previously topped out at 20px, and section
headings were *smaller and dimmer than their own body text* — an inverted
hierarchy that made long pages read as one undifferentiated column.

### Typography

Inter for prose, **IBM Plex Mono for every figure, eyebrow and table numeral**.
In a portfolio-identity product the disclosed numbers are the content, so they
carry the typographic personality rather than a decorative headline face.
`tabular-nums` is set on `.font-mono` globally, so digits never reflow as
values change on sync.

### Portfolio Identity Strip

A portfolio's sector mix drawn to scale as one band, at three variants —
`tiny` (dense lists), `medium` (profile header, comparison), `large`
(analytics). Colours come from `lib/sectorColors.ts`, the same mapping the
donut chart and the holdings-table dots use, so the three views reinforce one
legend instead of teaching three. The `aria-label` carries the top three
sectors, so it conveys the same information non-visually.

**It renders `null` when allocation data is absent.** No placeholder, no
equal-weight fallback, no shape derived from holding counts. A strip built
from data we don't have would assert a composition the platform can't stand
behind, which is worse than an absent element on a product whose entire claim
is that what you see is what someone actually holds.

### Backend fields needed for future UI

Each of these is currently blocking a specific piece of UI. None were changed
as part of the frontend work.

| Field | Endpoint | Unlocks |
|---|---|---|
| `sector_allocation` | `GET /discovery/investors` (list item) | The identity strip on discovery cards — the highest-value placement, since it makes a grid scannable by portfolio shape. The endpoint returns `health` but not allocation |
| `sector_allocation` | `GET /public-investors` (list item) | Same, for the library grid |
| Analytics for seeded portfolios | Library portfolio profiles | **All five** Public Investor Library portfolios return `sector_allocation: {}` and `health: null`, because analytics are computed during `run_sync` and seeded portfolios never sync. So no library profile shows health metrics, an allocation chart, or the identity strip — despite their holdings carrying real sector data |
| `current_price` / market value per holding | `GET /portfolios/:id/profile` | The holdings table's Value column shows `—` for every library holding, because `avg_cost_price` is null there. `total_value` is cost-basis only, which is why the dashboard labels it as such |

### Remaining UI debt

- **The `tiny` identity-strip variant is unused.** It exists for discovery and
  library cards, which is where a scannable portfolio shape would be most
  valuable — but those endpoints don't return `sector_allocation` (see the
  table above), so nothing can render it yet.
- **Discovery filters are component state, not URL state.** Strategy, sort and
  page live in `useState`, so a filtered view can't be shared or deep-linked
  and the back button doesn't step through filter changes.
- **Holdings table is not virtualised.** Fine at current volumes; a portfolio
  past ~50 positions would want it.
- **`Avatar`'s `<img>` has no explicit `width`/`height`**, so an avatar with a
  real image URL can shift layout as it loads. Initials-only avatars are
  unaffected.
- **Motion is CSS, not Framer Motion**, which this doc originally specified.
  Fades, small rises and a skeleton shimmer don't justify ~35 kB of JS on a
  data product. Revisit only if layout-animation or gestures appear.
