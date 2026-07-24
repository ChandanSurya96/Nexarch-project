# Decisions (ADR Log)

**Purpose:** Every significant technical or product decision, recorded with its reasoning, alternatives considered, and consequences — so a future engineer (or founder revisiting a choice six months from now) doesn't have to reconstruct *why* from git blame. New entries go at the bottom; existing entries are never edited after the fact — a changed decision gets a new ADR that references the old one, the same way the schema itself only moves forward via new migrations (see [database.md](./database.md)).

---

### ADR-001 — Flask over FastAPI/Django for the backend
**Date:** 2026-07-14
**Decision:** Use Flask, as specified at founding.
**Reasoning:** Founding scope mandates it; also genuinely reasonable for this project's size — lightweight, flexible, well-understood.
**Alternatives considered:** FastAPI (async support, auto-generated OpenAPI docs out of the box), Django (batteries-included, admin panel).
**Consequences:** Nexarch loses FastAPI's automatic OpenAPI generation and native async, and Django's built-in admin — the admin gap in particular means any internal moderation/support tooling needs to be built deliberately rather than inherited for free. Mitigate by keeping [api.md](./api.md) rigorously up to date as the manual substitute for auto-generated docs, and treating an admin panel as an explicit Phase 1/2 backlog item, not an assumption.

### ADR-002 — Read-only broker sync only for MVP; no trade execution
**Date:** 2026-07-14
**Decision:** No order placement, no copy trading, until Phase 5 at the earliest.
**Reasoning:** Execution brings SEBI stockbroker/portfolio-manager-adjacent regulatory obligations that are an entirely different scope of legal and compliance work than read-only data aggregation. Staying read-only lets Nexarch validate the trust/discovery thesis (does anyone want this?) before taking on that cost.
**Alternatives considered:** Launching with copy-trading from day one, closer to the US app Dub's model (see [product/competitor-analysis.md](./product/competitor-analysis.md)) — rejected as premature given Dub itself operates under SEC/FINRA registration specifically to support that model.
**Consequences:** Monetization can't include brokerage/execution commission early; Phase 4's Creator Economy has to work on subscriptions/access rather than trade-copying revenue.

### ADR-003 — PostgreSQL as the primary datastore
**Date:** 2026-07-14
**Decision:** PostgreSQL, as specified at founding.
**Reasoning:** Relational integrity matters for financial holdings data; strong JSONB support covers the flexible fields (`sector_allocation`, `health_metrics`) without needing a second database; mature ecosystem on both Railway and AWS.
**Alternatives considered:** None seriously — this was a founding-scope decision, recorded here for completeness rather than genuine deliberation.
**Consequences:** None negative identified at this scale.

### ADR-004 — JWT auth with short-lived access token + rotating refresh token
**Date:** 2026-07-14
**Decision:** As detailed in [security.md](./security.md).
**Reasoning:** Standard, well-understood pattern for a decoupled SPA/API architecture; stateless access tokens scale horizontally without session storage.
**Alternatives considered:** Server-side session cookies only (simpler, but couples the API to sticky sessions or a shared session store, which fights the stateless-scaling goal in [architecture.md](./architecture.md)).
**Consequences:** Requires careful refresh-token storage (httpOnly cookie, not localStorage) to avoid reintroducing the XSS exposure JWTs are otherwise prone to.

### ADR-005 — Redis + Celery for background jobs and caching
**Date:** 2026-07-14
**Decision:** Add Redis and a Celery-based job queue, not specified in the founding brief but required by the architecture.
**Reasoning:** Broker sync involves slow, rate-limited, third-party network calls that cannot run inline on a request without harming API latency and reliability. A queue decouples sync throughput from API traffic.
**Alternatives considered:** RQ (simpler, smaller ecosystem than Celery) — worth reconsidering if Celery's operational overhead feels disproportionate to Phase 1's actual job volume; not a hill to die on either way.
**Consequences:** One more moving part to run and monitor in every environment, including local dev (mitigated via Docker Compose, see [development-guide.md](./development-guide.md)).

### ADR-006 — Single `portfolios` table with nullable owner FKs, not separate verified/public tables
**Date:** 2026-07-14
**Decision:** See full reasoning in [database.md](./database.md).
**Reasoning:** Avoids duplicating holdings/snapshot/strategy-tag relationships across two parallel table sets for data that's treated identically by every downstream consumer once loaded.
**Alternatives considered:** Separate `verified_portfolios` / `public_portfolios` tables.
**Consequences:** Requires an application-level (or DB check) constraint to prevent a portfolio having both a `user_id` and a `public_investor_id`, or neither.

### ADR-007 — No single "trust score"; objective health indicators only
**Date:** 2026-07-14
**Decision:** Portfolio Health surfaces multiple labeled, independently-explained indicators (diversification, concentration, age, consistency) rather than one composite number.
**Reasoning:** Directly follows from the founding philosophy in [vision.md](./vision.md); also a real regulatory consideration, not just a philosophical one — see [security.md](./security.md) on why a single score sits closer to "advice" than a set of transparent indicators.
**Alternatives considered:** A composite 0–100 "Nexarch Score," which several competitor/adjacent products in other markets do use — rejected specifically because it's the more common, more expected pattern, and Nexarch's differentiation depends on not doing the expected thing here.
**Consequences:** Slightly harder onboarding UX (users may initially expect and look for a single number) — worth deliberate design attention rather than treating it as a solved problem by omission.

### ADR-008 — True volatility/risk metrics deferred pending a market-data vendor
**Date:** 2026-07-14
**Decision:** Diversification and sector concentration ship in Phase 1 (computable from holdings alone); volatility and risk-adjusted metrics wait for Phase 2+.
**Reasoning:** Broker read-only sync provides current holdings, not historical price series. Computing genuine volatility needs a market-data source Nexarch doesn't have yet.
**Alternatives considered:** Approximating "risk" from sector concentration alone and labeling it as risk — rejected as misleading; a concentration proxy is not the same thing as volatility, and presenting it as such would be exactly the kind of fabricated-looking precision [product-requirements.md](./product-requirements.md) explicitly warns against.
**Consequences:** Phase 1 Portfolio Health is honestly incomplete on this dimension rather than falsely complete. Phase 2 needs a market-data vendor decision as its own follow-up ADR.

### ADR-009 — React Query (or SWR) for server state; no global client-state library
**Date:** 2026-07-14
**Decision:** Proposed default, not specified at founding — see [architecture.md](./architecture.md).
**Reasoning:** Nexarch's frontend state is overwhelmingly server data (portfolios, discovery feed, holdings) with caching/refetch needs React Query handles natively; local-only UI state (modal open/closed, form inputs) doesn't need a global store at this scale.
**Alternatives considered:** Redux/Zustand for everything — rejected as unnecessary complexity for Phase 1's actual state-management needs; revisit only if a concrete cross-cutting client-state need emerges.
**Consequences:** None identified; low-risk, easily reversible choice.

### ADR-010 — Evaluate Account Aggregator integration in parallel with the first direct broker integration
**Date:** 2026-07-14
**Decision:** Don't commit fully to broker-by-broker API integration as the only sync path before testing the AA framework in parallel. See full reasoning in [broker-integrations.md](./broker-integrations.md).
**Reasoning:** NSDL and CDSL are both now live, SEBI-specified FIPs on the RBI Account Aggregator network for securities holdings — a broker-agnostic, standardized, regulator-blessed consent path that sidesteps needing a separate integration (and separate commercial terms) per broker.
**Alternatives considered:** Direct broker API integration only, broker by broker, per the founding brief's literal broker list.
**Consequences:** Adds an FIU-registration/compliance evaluation to the Phase 1 workplan that wasn't in the original scope — worth the added upfront work given the downstream simplification if it pans out. Needs a founder decision on whether to pursue directly or through a TSP that already holds FIU status.

### ADR-011 — Public display of synced holdings is not yet cleared against broker data-vending terms
**Date:** 2026-07-14
**Decision:** Do not default new broker connections to public visibility until this is resolved; keep `is_public` opt-in and off by default regardless (this was already the plan per [product-requirements.md](./product-requirements.md), but this ADR records the specific reason it's now non-negotiable rather than just a sensible default).
**Reasoning:** Zerodha's Kite Connect terms describe the API as an execution platform, "not a data distribution service," and describe displaying/redistributing its data on external platforms as a violation of exchange data-vending policy. See [broker-integrations.md](./broker-integrations.md).
**Alternatives considered:** Proceeding without broker sign-off on the assumption that a user sharing their own data is obviously fine — rejected; "obviously fine" is exactly the kind of assumption that deserves a real answer before it's load-bearing for the product's core feature.
**Consequences:** A direct conversation with each broker (starting with Zerodha) is a pre-launch blocker for the *public-profile* feature specifically, even though it's not a blocker for building the private sync/verification architecture now.

### ADR-012 — Pilot broker set to Upstox; Account Aggregator evaluated in parallel, absent objection
**Date:** 2026-07-15
**Decision:** Treat Upstox-as-pilot-broker and AA-evaluated-in-parallel (per ADR-010) as the working plan for Phase 1.
**Reasoning:** Both were proposed with reasoning in prior discussion; neither drew an objection after being explicitly raised as open questions. Recorded here honestly as *proceeding absent objection*, not as an explicit founder sign-off — worth distinguishing from ADRs above that do reflect founder-confirmed direction, since this document's value depends on accurately recording how a decision was actually reached.
**Alternatives considered:** Continuing to hold both open pending explicit confirmation — rejected as unproductive; these are low-stakes, easily-reversed choices (an adapter swap and a spike, not an architectural commitment), unlike the actual gate on writing production code itself, which this ADR does not resolve.
**Consequences:** Phase 1 broker-adapter work can proceed against Upstox; the AA-integration spike is scheduled alongside it rather than deferred. Either can still be revisited cheaply if reconsidered later.
