# Feature Backlog

**Purpose:** Ticket-level breakdown within each roadmap phase — more granular than [roadmap.md](../roadmap.md), less detailed than the full acceptance criteria in [product-requirements.md](../product-requirements.md). Use this to plan sprints; use product-requirements.md to actually build against.

---

## Phase 1 — Foundation & MVP

| Feature | Priority | Status | Notes |
|---|---|---|---|
| Auth: register/login/refresh/logout | P0 | Backend done (Milestone 1); frontend done (Milestone 4a) | See [api.md](../api.md); login/register pages, silent refresh on load, in-memory-only access token (ADR-017) |
| Database schema + initial migration | P0 | Done (Milestone 1; extended in Milestone 2 with `audit_logs`) | See [database.md](../database.md) |
| Broker connection: Upstox (pilot broker) | P0 | Done (Milestone 2 backend; Milestone 4b frontend) | Free API, analytics token avoids daily reauth — see [broker-integrations.md](../broker-integrations.md). Connect/reconnect/disconnect/sync-now UI in `app/profile/page.tsx`; a real OAuth round-trip couldn't be verified live in dev (no broker credentials) |
| Sync worker (Celery) + normalization layer | P0 | Done (Milestone 2) | Shared `Holding` interface across adapters |
| Verified profile page | P0 | Done (Milestone 4b) | `app/profile/page.tsx` (own) + `app/portfolios/[id]/page.tsx` (viewer) sharing `PortfolioProfileView`; Badge, holdings table, allocation chart, health stats |
| Public/private toggle | P0 | Done (Milestone 2 backend; Milestone 4b frontend) | `PATCH /api/v1/portfolios/:id`; private by default; frontend control now live, behind a confirm `Modal`. Gated on ADR-011 resolution for full *public rollout* (the toggle itself works; the broker data-vending question is separate) |
| Public Investor Library (seed data: 5 initial profiles) | P0 | Done (Milestone 3 backend; Milestone 4c frontend) | 5 real, cited profiles seeded via `scripts/seed_public_investors.py`; `app/library/page.tsx` lists them, linking to `app/portfolios/[id]/page.tsx` via the new `portfolio_id` field (ADR-022) |
| Discovery feed v1 (list + strategy filters) | P0 | Done (Milestone 3 backend; Milestone 4c frontend) | No "most followed" sort yet (cold start, by design). `app/discover/page.tsx`: strategy chips, sort select, pagination |
| Portfolio analytics: allocation, sector split, HHI diversification/concentration | P0 | Done (Milestone 2 backend; Milestone 4b frontend) | See calculation notes in [product-requirements.md](../product-requirements.md); rendered via `AllocationChart` + `StatCard` grid |
| Portfolio Health card (no single score) | P1 | Done (Milestone 2 backend; Milestone 4b frontend; volatility added Milestone 5) | Metrics computed per ADR-007; rendered as independent `StatCard`s (now five, including volatility per ADR-024), never a composite number |
| Investor Strategy Overview (rules-based) | P1 | Done (Milestone 3 backend; Milestone 4b frontend) | Folded into `GET /portfolios/:id/analytics`; descriptive-only per [security.md](../security.md); shown as plain text on the profile page |
| Following (follow/unfollow, no capital) | P0 | Done (Milestone 3 backend; Milestone 4b frontend) | `POST/DELETE /portfolios/:id/follow`, `GET /users/me/following`; follow status derived client-side from the following list (no per-portfolio `is_following` field in `PortfolioSchema` yet) |
| Portfolio activity (snapshot-diff, ADR-015) | — | Backend done (Milestone 3) | Not in the original Phase 1 backlog — added during Milestone 3 as the compliant subset of a Parrot Finance/Dub-inspired design exploration. `GET /portfolios/:id/activity` |
| Responsive layout + dark mode theme | P0 | Dark theme done (Milestone 4a); responsive checked on Discover/Library (Milestone 4c) | Design tokens + Tailwind wired up (dark-only, no toggle yet). `app/discover` and `app/library` — the pages `design-system.md` calls out by name for mobile-first design — checked at a narrow viewport this milestone; the profile pages (4b) still haven't had a dedicated pass |
| Second broker connection: Dhan | P1 | Not started | Milestone 5. Free, generous rate limit |
| Account Aggregator integration spike | P1 | Not started | Milestone 5, pending founder decision on FIU-registration path. Parallel evaluation per ADR-010 — timebox to validate feasibility before committing further |
| Portfolio history (`GET .../history`, raw snapshots over time) | — | Done — Milestone 5 | Documented in [api.md](../api.md) since Phase 0, built alongside the volatility work; distinct from `.../activity` (raw data vs. descriptive diff). `total_value`/`diversification_score`/`volatility` per snapshot, oldest to newest |

## Phase 2 — Advanced Analytics & Comparisons

| Feature | Priority | Notes |
|---|---|---|
| Additional broker connections (Angel One, Fyers, Zerodha, Groww) | P1 | Not started — Milestone 8. Zerodha gated on data-vending clarification (ADR-011); Groww gated on validating user willingness to pay Groww's ₹499/mo API fee |
| Portfolio comparison (side-by-side) | P1 | Done — Milestone 6. `GET /portfolios/compare?ids=a,b` (ADR-026), computed on read, no new table. Diffs total value, sector allocation, and health metrics; honestly-empty/`null` wherever a side has no snapshot (never a fabricated zero). Link-only entry from `InvestorCard`/portfolio detail page this milestone, no dedicated picker (ADR-027) |
| Rules-based strategy auto-categorization | P1 | Done — Milestone 7 (3 of 8 categories). Small-cap Specialist, Low-risk, Momentum auto-computed on every sync (`strategy_categorization_service.py`); Growth/Value/Dividend/ETF/Long-term deferred pending real data sources (ADR-028). Precedes AI-based version in Phase 3 |
| Watchlists | P2 | Not started |
| Market-data vendor selection for volatility metrics | P1 | Done — Milestone 5. Resolved via ADR-024: reused Upstox's own historical-candle API rather than a separate vendor. `health.volatility`, annualized, value-weighted; verified-portfolios only (see ADR-024's Public Investor Library limitation) |
| "Most followed" discovery sort | P2 | Only once follow counts are meaningful |

## Phase 3 — AI-Assisted Insight

| Feature | Priority | Notes |
|---|---|---|
| AI-generated portfolio explanations | P1 | Must inherit the same descriptive-only constraint as the Phase 1 rules-based version — see [security.md](../security.md) |
| Personalized discovery recommendations | P2 | "Similar to investors you follow" |
| Investment education assistant | P2 | Scoped to platform data only, not general financial advice |

## Phase 4 — Creator Economy

| Feature | Priority | Notes |
|---|---|---|
| Legal review: SEBI RA/IA implications of paid research/insights | **P0 — hard gate** | Must complete before any item below ships — see [monetization.md](./monetization.md) |
| Premium subscriptions (platform-level) | P1 | |
| Creator monetization (profile access, communities) | P1 | Gated on legal review above |
| Platform commission | P2 | |

## Phase 5 — Optional Trade Execution

| Feature | Priority | Notes |
|---|---|---|
| Regulatory scoping (separate legal project) | **P0 — hard gate** | Treat as its own workstream, not an engineering ticket |
| Execution via supported brokers | TBD | Fully dependent on the above |
| Real-time sync / webhooks | TBD | |

## Backlog Grooming Note

Anything added here should already have a home in [roadmap.md](../roadmap.md)'s phase structure — if it doesn't fit any phase's stated goal, that's a signal to either update the roadmap deliberately (with a note in [decisions.md](../decisions.md)) or park the idea rather than let scope drift in through the backlog side door.
