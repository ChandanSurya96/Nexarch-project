# Nexarch Documentation

**Purpose:** This folder is the single source of truth for Nexarch — product thinking, architecture, database, API, and process — in one place. A new engineer or AI agent should be able to read this folder start to finish and understand the entire project without asking anyone a question.

---

## What is Nexarch

Nexarch is India's portfolio identity and investor-discovery platform. Users connect a brokerage account (read-only) to generate a verified investing profile, and browse other investors by strategy, diversification, and consistency instead of by follower count. See [vision.md](./vision.md) for the full philosophy.

## Current Status — Phase 2.5 complete · **Beta Candidate**

- **Stage:** Phase 1 (Milestones 1–4c) is complete and tagged `phase-1-complete` — auth, broker connection/sync, portfolio analytics, Public Investor Library, discovery feed, follows, and the full frontend. Phase 2 (Milestones 5–8) is complete: Health Metrics (ADR-024), Portfolio Comparison (ADR-026/027), Strategy Categorization (ADR-028), and the Dhan integration. **Phase 2.5 (Production Hardening) is now complete**, across five slices: Security & API (ADR-029–033), Reliability & Observability (ADR-034), Performance & Database (ADR-035–038), Deployment & Operations (ADR-039–043), and Review Fixes & Operational Hardening (ADR-044–047). See [roadmap.md](./roadmap.md) and [changelog.md](./changelog.md).
- **This entry (Review Fixes & Operational Hardening):** the last engineering slice before real users. Login response timing no longer reveals whether an email is registered — the unknown-email path skipped bcrypt entirely and answered in 2.8 ms against 338.8 ms for a real account, a **122x** account-enumeration oracle, now 1.08x (ADR-044 covers the separate encryption work; `scripts/benchmark_login_timing.py` reproduces both numbers). `ENCRYPTION_KMS_KEY_ID` is now rotatable with **zero user reconnects**, verified by rotating a genuinely old token and then deleting the original key (ADR-044) — this supersedes ADR-043, which had recorded the limitation and deferred the fix. `GET /health/sync` makes the sync pipeline's worst failure mode — silence — observable (ADR-047), and the daily sync is spread across a window rather than firing every connection at 02:00:00 (ADR-046). CI's first run against real Postgres immediately found a **latent production bug**: `reconnect` had been missing from `audit_event_type_enum` since Milestone 2, so every broker reconnect returned a 500. Three hardening slices of SQLite-only testing had hidden it.
- **Stack:** Next.js / TypeScript / Tailwind (frontend), Flask / SQLAlchemy / PostgreSQL (backend), Redis + Celery (background sync, discovery-feed and price caches, sync heartbeats), JWT auth.
- **Next step — not more engineering.** The project state is **Beta Candidate**. What remains is operational: merge the open PRs, provision Railway/Vercel, perform the first real deployment, execute the production checklist in [operations.md](./operations.md), invite a handful of trusted beta users, and collect real feedback before building anything else. The **deployment rehearsal is explicitly blocked** until that infrastructure exists — see [roadmap.md](./roadmap.md).

Three findings from this round of research changed the plan materially enough that they're worth knowing before you read anything else:

1. **The RBI Account Aggregator (AA) framework is now live for securities holdings** — NSDL and CDSL are both SEBI-specified Financial Information Providers on the AA network. This is a broker-agnostic way to pull consented holdings data and may be a better long-term primary path than integrating each broker one by one. See [broker-integrations.md](./broker-integrations.md).
2. **Displaying synced holdings publicly may conflict with at least one broker's data-vending terms.** Zerodha's Kite Connect terms describe it as an execution platform, not a data-redistribution service. This needs a direct conversation with each broker before public profiles go live — flagged in [broker-integrations.md](./broker-integrations.md) and [decisions.md](./decisions.md) as an open risk, not a solved problem.
3. **SEBI's finfluencer crackdown (2024–2026) is directly relevant to this product's copy**, not just to influencers. The line between "descriptive portfolio data" and "investment advice" is exactly the line Nexarch's core features sit next to. See [security.md](./security.md) and [product/monetization.md](./product/monetization.md).

## Documentation Index

### Product & Vision
| Doc | Purpose |
|---|---|
| [vision.md](./vision.md) | Mission, philosophy, positioning, long-term goals |
| [roadmap.md](./roadmap.md) | MVP → Phase 5, what's explicitly deferred |
| [product-requirements.md](./product-requirements.md) | Feature-by-feature spec with acceptance criteria |

### Engineering
| Doc | Purpose |
|---|---|
| [architecture.md](./architecture.md) | System design, data flow, scalability, diagrams |
| [database.md](./database.md) | Schema, ER diagram, indexing, migrations |
| [api.md](./api.md) | REST conventions, endpoints, auth, errors, pagination |
| [broker-integrations.md](./broker-integrations.md) | Broker/AA integration architecture, sync strategy |
| [design-system.md](./design-system.md) | Visual language, components, accessibility |
| [security.md](./security.md) | AuthN/Z, encryption, compliance, incident response |
| [development-guide.md](./development-guide.md) | Local setup, folder structure, git workflow, testing |

### Process
| Doc | Purpose |
|---|---|
| [decisions.md](./decisions.md) | Architecture Decision Records (ADRs) |
| [operations.md](./operations.md) | Deploy, rollback, backup/restore, secret rotation, incident response |
| [changelog.md](./changelog.md) | Chronological log of what changed and when |

### Product Deep-Dives (`/product`)
| Doc | Purpose |
|---|---|
| [product/user-personas.md](./product/user-personas.md) | Who we're building for |
| [product/user-journey.md](./product/user-journey.md) | Step-by-step flow, including failure paths |
| [product/feature-backlog.md](./product/feature-backlog.md) | Ticket-level backlog by phase |
| [product/competitor-analysis.md](./product/competitor-analysis.md) | Who else solves pieces of this problem |
| [product/market-research.md](./product/market-research.md) | Market sizing and context, sourced |
| [product/monetization.md](./product/monetization.md) | Revenue model detail and regulatory notes |
| [product/go-to-market.md](./product/go-to-market.md) | Launch strategy |
| [product/success-metrics.md](./product/success-metrics.md) | KPIs by phase |
| [product/user-feedback.md](./product/user-feedback.md) | Feedback intake process and log template |

## How to Use This Documentation

- **Starting a new feature?** Read `product-requirements.md` for the spec, `architecture.md` + `database.md` for how it fits, then update `decisions.md` if you made a non-obvious call.
- **Onboarding as an engineer (human or AI agent)?** Read in this order: `vision.md` → `architecture.md` → `database.md` → `api.md` → `development-guide.md`.
- **Documentation is part of the product.** Per the founding process, any significant architectural, database, API, or product decision must update the relevant doc *before* the next feature is built on top of it. Docs that fall out of sync with reality are worse than no docs — if you notice one has drifted, fix it in the same PR.
