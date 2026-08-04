# Nexarch Documentation

**Purpose:** this folder is the single source of truth for Nexarch — product thinking, architecture, database, API, and process. A new engineer or AI agent should be able to read it and understand the entire project without asking anyone a question.

**This file is an index.** It points at the document that owns each subject; it doesn't restate their contents. If you find status, architecture, or history written out here, it's in the wrong place.

---

## What is Nexarch

India's portfolio identity and investor-discovery platform. Users connect a brokerage account (read-only) to generate a verified investing profile, and browse other investors by strategy, diversification, and consistency instead of by follower count. See [vision.md](./vision.md) for the full philosophy.

## Start here

**→ [CURRENT_STATE.md](./CURRENT_STATE.md)** — project stage, what's done, what's blocked, what's next, and today's test and CI results. Read it first; everything else describes intent, that describes reality.

It also carries the recommended reading order for a fresh session.

## Three things to know before reading anything else

Findings that materially shaped the plan, each owned by the doc it links to:

1. **The RBI Account Aggregator framework is live for securities holdings** — NSDL and CDSL are both SEBI-specified Financial Information Providers on the AA network. A broker-agnostic way to pull consented holdings, and possibly a better long-term primary path than integrating brokers one at a time. → [broker-integrations.md](./broker-integrations.md)
2. **Displaying synced holdings publicly may conflict with at least one broker's data-vending terms.** Zerodha's Kite Connect terms describe it as an execution platform, not a data-redistribution service. An open risk, not a solved problem — and the reason new connections default to private. → [broker-integrations.md](./broker-integrations.md), [decisions.md](./decisions.md) (ADR-011)
3. **SEBI's finfluencer crackdown (2024–2026) applies to this product's copy**, not just to influencers. The line between "descriptive portfolio data" and "investment advice" is exactly the line Nexarch's core features sit beside. → [security.md](./security.md), [product/monetization.md](./product/monetization.md)

## Documentation index

### Status & process
| Doc | Owns |
|---|---|
| [CURRENT_STATE.md](./CURRENT_STATE.md) | **Today** — stage, status, blockers, priorities, test/CI results |
| [decisions.md](./decisions.md) | **Why** — Architecture Decision Records |
| [roadmap.md](./roadmap.md) | **Future** — phases, and what's explicitly deferred |
| [changelog.md](./changelog.md) | **History** — what changed and when |
| [TECHNICAL_DEBT.md](./TECHNICAL_DEBT.md) | **Known debt** — verified, prioritised, with suggested fixes |
| [OPERATIONAL_GOTCHAS.md](./OPERATIONAL_GOTCHAS.md) | **Workflow traps** — the things that cost an hour |
| [operations.md](./operations.md) | **Runbooks** — deploy, rollback, backup/restore, secret rotation, incidents |

### Product & vision
| Doc | Owns |
|---|---|
| [vision.md](./vision.md) | Mission, philosophy, positioning, long-term goals |
| [product-requirements.md](./product-requirements.md) | Feature-by-feature spec with acceptance criteria |

### Engineering
| Doc | Owns |
|---|---|
| [architecture.md](./architecture.md) | System design, data flow, scalability, diagrams |
| [database.md](./database.md) | Schema, ER diagram, indexing, migrations |
| [api.md](./api.md) | REST conventions, endpoints, auth, errors, pagination |
| [broker-integrations.md](./broker-integrations.md) | Broker/AA integration architecture, sync strategy |
| [design-system.md](./design-system.md) | Visual language, components, accessibility |
| [security.md](./security.md) | AuthN/Z, encryption, compliance, incident response |
| [development-guide.md](./development-guide.md) | Local setup, folder structure, git workflow, testing |

### Product deep-dives (`/product`)
| Doc | Owns |
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

Working rules, conventions and commands live in [CLAUDE.md](../CLAUDE.md) at the repository root.

## Documentation boundaries

Each document owns exactly one thing. Keeping these separate is what stops a status line from rotting inside an architecture doc.

| Document | Owns | Does **not** own |
|---|---|---|
| `README.md` (this file) | Navigation | Status, architecture, history |
| `CURRENT_STATE.md` | Today's reality | Long-term design, future plans |
| `roadmap.md` | Future work and deferrals | Current status |
| `decisions.md` | Reasoning, alternatives, consequences | Status, instructions |
| `changelog.md` | Chronological history | Current status |
| `CLAUDE.md` | How to work here | Anything volatile |
| `TECHNICAL_DEBT.md` | Known debt | Unbuilt features |
| `OPERATIONAL_GOTCHAS.md` | Workflow traps | Setup steps, runbooks |

When something belongs in two places, put it in the owning document and **link** from the other.

## Keeping documentation honest

- **Docs are part of the product.** Any significant architectural, database, API or product decision updates the relevant doc *before* the next feature is built on top of it.
- **Fix drift in the same PR you notice it.** A doc that has drifted is worse than no doc, because it reads as authoritative. Real examples found here: CSRF and rate limiting documented as present while absent, a Framer Motion dependency specified but not installed, endpoints documented in `api.md` that don't exist, and a broker integration described as shipped that was never merged.
- **Verify against the implementation, never the other way round.** When docs and code disagree, the code is the fact and the doc is the bug.
- **`Last verified: YYYY-MM-DD`** appears at the top of every doc whose accuracy depends on the state of the code rather than on philosophy. If you re-check its claims, move the date. If it's badly stale, treat its contents as a hypothesis.
