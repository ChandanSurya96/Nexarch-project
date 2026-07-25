# Nexarch Documentation

**Purpose:** This folder is the single source of truth for Nexarch — product thinking, architecture, database, API, and process — in one place. A new engineer or AI agent should be able to read this folder start to finish and understand the entire project without asking anyone a question.

---

## What is Nexarch

Nexarch is India's portfolio identity and investor-discovery platform. Users connect a brokerage account (read-only) to generate a verified investing profile, and browse other investors by strategy, diversification, and consistency instead of by follower count. See [vision.md](./vision.md) for the full philosophy.

## Current Status — Phase 2, Milestone 5 done

- **Stage:** Phase 1 (Milestones 1–4c) is complete and tagged `phase-1-complete` — auth, broker connection/sync, portfolio analytics, Public Investor Library, discovery feed, follows, and the full frontend. Phase 2 has begun: Milestone 5 (Health Metrics) resolved ADR-008 by adding portfolio volatility (ADR-024, reusing Upstox's own historical-price API) and built the long-documented `GET /portfolios/:id/history` endpoint + chart. See [changelog.md](./changelog.md) for what shipped in each.
- **Stack:** Next.js / TypeScript / Tailwind (frontend), Flask / SQLAlchemy / PostgreSQL (backend), Redis + Celery (background sync + discovery-feed cache), JWT auth.
- **Next step:** per the agreed Phase 2 sequencing — Milestone 6 (Portfolio Comparison), Milestone 7 (Strategy Categorization), Milestone 8 (Additional Broker: Dhan) — see [roadmap.md](./roadmap.md) and [decisions.md](./decisions.md).

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
