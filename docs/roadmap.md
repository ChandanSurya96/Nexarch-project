# Roadmap

**Purpose:** This is the phase-by-phase plan from MVP to long-term vision — what gets built, in what order, and just as importantly, what is explicitly *not* being built yet and why. See [feature-backlog.md](./product/feature-backlog.md) for ticket-level detail within each phase, and [decisions.md](./decisions.md) for the reasoning behind sequencing calls.

---

## How to Read This

Each phase has a goal, not just a feature list. A phase is "done" when its goal is demonstrably true, not when every listed item is checked off — some items will move between phases as we learn more, and that's expected and fine as long as it's recorded in [decisions.md](./decisions.md).

```mermaid
graph LR
    P0[Phase 0<br/>Docs & Architecture] --> P1[Phase 1<br/>Foundation & MVP]
    P1 --> P2[Phase 2<br/>Analytics & Depth]
    P2 --> P3[Phase 3<br/>AI-Assisted Insight]
    P3 --> P4[Phase 4<br/>Creator Economy]
    P4 --> P5[Phase 5<br/>Optional Execution]

    style P0 fill:#2d2d3a,stroke:#8886ff,color:#fff
    style P1 fill:#1f3a2e,stroke:#4ade80,color:#fff
    style P2 fill:#2d2d2d,stroke:#999,color:#fff
    style P3 fill:#2d2d2d,stroke:#999,color:#fff
    style P4 fill:#2d2d2d,stroke:#999,color:#fff
    style P5 fill:#3a1f1f,stroke:#f87171,color:#fff
```

---

## Phase 0 — Architecture & Documentation *(current)*

**Goal:** Nobody writes application code against an undocumented, unreviewed plan.

- Full `/docs` knowledge base (this folder)
- Database schema design
- API contract design
- Broker/AA integration strategy, including the open risks
- Founder sign-off on the decisions in [decisions.md](./decisions.md)

**Exit criteria:** Founder approves the schema, the broker-integration approach, and the list of open compliance questions — explicitly, before Phase 1 branches are opened.

## Phase 1 — Foundation & MVP

**Goal:** A user can connect one broker, get a verified badge, and see their own profile — and can browse the Public Investor Library even before any community adoption exists (solves cold start).

In scope:
- Auth (register/login, JWT access + refresh)
- Database + migrations for the core schema
- Broker connection architecture for **one** broker first (recommend starting with Upstox — free API, no daily token re-auth; see the broker comparison table in [broker-integrations.md](./broker-integrations.md)), built in a way that a second and third broker are additive, not a rewrite
- Verified profile generation from synced holdings
- Public Investor Library (seeded from public disclosures, manually curated at this stage)
- Discovery feed v1 (browse investors, basic filters)
- Portfolio pages with basic analytics (allocation, sector split)
- Responsive UI, dark mode

Explicitly excluded from Phase 1 (per founding scope, restated so it doesn't quietly creep in):
- Trade execution
- Copy trading
- AI assistants
- Subscriptions / paid tiers
- Notifications
- Chat / DMs
- Community posts / comments
- Enterprise features

**Exit criteria:** A real user can go from signup to a public, verified profile with holdings visible, end to end, with one broker.

## Phase 2 — Advanced Analytics & Comparisons

**Goal:** Discovery becomes genuinely useful, not just a directory.

- Additional broker integrations (see [broker-integrations.md](./broker-integrations.md) for the prioritized list)
- Portfolio comparison (side-by-side)
- Strategy categorization (rules-based, not ML yet)
- Watchlists (follow without needing an account relationship)
- Deeper portfolio-health metrics — this is also where a market-data dependency for volatility gets resolved (see [database.md](./database.md))

## Phase 2.5 — Production Hardening

**Goal:** Close the gap between what the docs claimed and what the code actually did, before adding more surface area (Account Aggregator, additional brokers) on top of it. Sequenced as four focused slices rather than one undifferentiated cleanup pass:

1. **Security & API** *(done — see [decisions.md](./decisions.md) ADR-029 through ADR-033)*: every failure path returns the documented response envelope; refresh-token rotation with family-based reuse detection; CSRF protection actually enabled (previously documented as if it were); rate limiting actually implemented (previously documented as if it were); a real database-level backstop for one-broker-connection-per-user; `GET /users/me/following` paginated like every other list endpoint; `/portfolios/compare`'s query parsing moved onto the same schema convention every other endpoint uses.
2. **Reliability** *(done — see [decisions.md](./decisions.md) ADR-034)*: sync-pipeline retry policy (rate-limit failures retry with backoff; token-expiry and unexpected errors don't); every sync failure path now consistently sets connection status, logs, and audit-logs (previously the most common failure class was silent); the daily scheduled sync no longer permanently drops a connection after one transient failure; `task_acks_late`/`task_reject_on_worker_lost` so a worker crash mid-sync doesn't lose the job forever; structured JSON logging with request-id correlation; `GET /health` and `GET /health/ready` endpoints. External alerting/APM deliberately deferred to the Deployment slice below, once a real hosting decision exists to tie it to.
3. **Performance** — N+1 query audit, sync latency, caching opportunities beyond the existing discovery-feed cache.
4. **Deployment & Operations** *(done — see [decisions.md](./decisions.md) ADR-039 through ADR-043)*: production now refuses to start on unsafe configuration — it previously booted with an empty JWT signing secret and issued forgeable tokens; CI (lint/typecheck/test/build against real Postgres and Redis) enforcing what `development-guide.md` had claimed since Phase 0 but nothing implemented; containerised Railway deploy with migrations run before traffic cutover; Sentry wired but inert until a DSN is set; backup/restore scripts with a restore drill that has actually been executed; and the secret-rotation runbook [security.md](./security.md) flagged as missing — including the honest finding that `ENCRYPTION_KMS_KEY_ID` cannot currently be rotated without breaking every broker connection. See [operations.md](./operations.md).

**Before private beta**, two items from this phase remain open and are deliberately *not* marked done:
- **Key-versioned encryption** so `ENCRYPTION_KMS_KEY_ID` can be rotated without forcing every user to reconnect their broker (ADR-043).
- **Provisioning the actual infrastructure** — the Railway project, Vercel project, and Sentry project don't exist yet, so the deploy pipeline has never run.

Beta launch follows this phase, not Account Aggregator or additional-broker work.

## Phase 3 — AI-Assisted Insight

**Goal:** Help users understand *why* a portfolio looks the way it does, without ever telling them what to do with that understanding.

- AI-generated, strictly descriptive portfolio explanations ("this portfolio has historically concentrated in financials and IT" — never "you should...")
- Personalized discovery recommendations (find investors similar to ones you already follow)
- Investment assistant — scoped narrowly to *education about the data on the platform*, not general advice; this is the feature most likely to drift into SEBI Research-Analyst / Investment-Adviser territory if not scoped carefully at design time, not just at copy-review time

## Phase 4 — Creator Economy

**Goal:** Verified investors can monetize credibility without Nexarch or its creators quietly becoming an unregistered advisory business.

- Premium subscriptions (platform-level)
- Creator monetization (premium profile access, research, communities)
- Platform commission model

**Hard gate before this phase ships:** legal review of the "exclusive research" and "subscription-based insights" mechanics against SEBI's Research Analyst Regulations, 2014 and Investment Adviser Regulations, 2013. See [product/monetization.md](./product/monetization.md) — this isn't boilerplate caution, it's the exact fact pattern SEBI has been actively enforcing against since 2024.

## Phase 5 — Optional Trade Execution

**Goal:** Only if Phases 1–4 prove the trust/discovery model works, and only with dedicated regulatory work.

- Optional execution through supported broker integrations
- Portfolio sync enhancements (webhooks, real-time)
- Automated investment workflows

This phase changes Nexarch's regulatory category substantially — moving from a read-only data platform to one that touches execution invites SEBI stockbroker / portfolio-manager-adjacent obligations. Treat this as a separate legal and architectural project, not an incremental feature, when the time comes.

---

## What's Deliberately Not on This Roadmap

Some ideas that will come up in founder conversations and should be written down here as *considered and deferred*, not forgotten:
- Trade execution before Phase 5 (see above)
- A single numeric "trust score" (conflicts with the philosophy in [vision.md](./vision.md) and [product-requirements.md](./product-requirements.md))
- Scraping any broker's app/site for users without a public API (see [broker-integrations.md](./broker-integrations.md) — Groww previously had no public API; it launched one in 2025, so this is now moot for Groww specifically, but the principle holds for any future broker without one)
