# Feature Backlog

**Purpose:** Ticket-level breakdown within each roadmap phase — more granular than [roadmap.md](../roadmap.md), less detailed than the full acceptance criteria in [product-requirements.md](../product-requirements.md). Use this to plan sprints; use product-requirements.md to actually build against.

---

## Phase 1 — Foundation & MVP

| Feature | Priority | Status | Notes |
|---|---|---|---|
| Auth: register/login/refresh/logout | P0 | Not started | See [api.md](../api.md) |
| Database schema + initial migration | P0 | Not started | See [database.md](../database.md) |
| Broker connection: Upstox (pilot broker) | P0 | Not started | Free API, analytics token avoids daily reauth — see [broker-integrations.md](../broker-integrations.md) |
| Sync worker (Celery) + normalization layer | P0 | Not started | Shared `Holding` interface across adapters |
| Verified profile page | P0 | Not started | Badge, holdings, allocation |
| Public/private toggle | P0 | Not started | Private by default; gated on ADR-011 resolution for full public rollout |
| Public Investor Library (seed data: 5 initial profiles) | P0 | Not started | Manual curation from public disclosures — see [product-requirements.md](../product-requirements.md) |
| Discovery feed v1 (list + strategy filters) | P0 | Not started | No "most followed" sort yet (cold start) |
| Portfolio analytics: allocation, sector split, HHI diversification/concentration | P0 | Not started | See calculation notes in [product-requirements.md](../product-requirements.md) |
| Portfolio Health card (no single score) | P1 | Not started | See ADR-007 |
| Responsive layout + dark mode theme | P0 | Not started | See [design-system.md](../design-system.md) |
| Second broker connection: Dhan | P1 | Not started | Free, generous rate limit |
| Account Aggregator integration spike | P1 | Not started | Parallel evaluation per ADR-010 — timebox to validate feasibility before committing further |

## Phase 2 — Advanced Analytics & Comparisons

| Feature | Priority | Notes |
|---|---|---|
| Additional broker connections (Angel One, Fyers, Zerodha, Groww) | P1 | Zerodha gated on data-vending clarification (ADR-011); Groww gated on validating user willingness to pay Groww's ₹499/mo API fee |
| Portfolio comparison (side-by-side) | P1 | |
| Rules-based strategy auto-categorization | P1 | Precedes AI-based version in Phase 3 |
| Watchlists | P2 | |
| Market-data vendor selection for volatility metrics | P1 | Unblocks ADR-008 |
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
