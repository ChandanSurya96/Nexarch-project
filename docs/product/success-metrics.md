# Success Metrics

**Purpose:** What "working" looks like, phase by phase — so success isn't judged by vanity metrics that conflict with [vision.md](../vision.md)'s explicit rejection of fake social signals. See [go-to-market.md](./go-to-market.md) for the strategy these metrics are meant to evaluate.

---

## Phase 1 — Foundation & MVP

The goal is proving the core loop works at all, not scale:

| Metric | Why it matters |
|---|---|
| **Activation rate** — % of new accounts that connect a broker within 7 days | Tests whether the value proposition is clear enough to prompt the highest-friction action in the journey |
| **Profile completion rate** — % of connected accounts that generate a full profile (badge, holdings, analytics) without error | A proxy for broker-integration reliability, not just product appeal |
| **Sync success rate** — % of scheduled syncs that complete without error | Directly tied to the >95% target in [product-requirements.md](../product-requirements.md) non-functional requirements |
| **Public Investor Library engagement** — page views / time-on-profile for Public Investor entries | Tests whether the cold-start strategy in [go-to-market.md](./go-to-market.md) is actually working, independent of community adoption |
| **Discovery-to-follow conversion** — % of discovery-feed sessions that result in at least one follow | Tests whether the browse experience itself is compelling, separate from whether users go on to connect their own broker |

## Phase 2 — Advanced Analytics & Comparisons

| Metric | Why it matters |
|---|---|
| **Returning-user rate (WAU/MAU)** | Tests the pull-based return loop described in [user-journey.md](./user-journey.md), given no push notifications exist yet |
| **Multi-broker connection rate** | Signals whether users trust the platform enough to consolidate more of their financial identity into it |
| **Portfolios per strategy category** | Watches for a lopsided feed (e.g., everything tagged "Growth," nothing tagged "Dividend") that would undermine discovery's usefulness |

## Phase 3 — AI-Assisted Insight

| Metric | Why it matters |
|---|---|
| **AI explanation engagement/helpfulness** | Should be measured alongside a manual compliance spot-check of generated copy against the descriptive-only constraint in [security.md](../security.md) — a metric that only tracks engagement without also tracking compliance drift would be actively dangerous here |

## Phase 4 — Creator Economy

| Metric | Why it matters |
|---|---|
| **% of paid creators with verified SEBI RA/IA registration where applicable** | This is a compliance metric that belongs alongside revenue metrics, not a separate afterthought — see [monetization.md](./monetization.md) |
| **Premium conversion rate** | Standard SaaS-style metric, meaningful only once Phase 2's analytics depth gives Premium something worth paying for |
| **Creator payout volume** | Standard marketplace health signal |

## Explicitly Avoided as Success Metrics

Consistent with [vision.md](../vision.md)'s rejection of fake social signals:
- **Raw follower counts** as a headline metric, in isolation — easy to inflate, and the entire product thesis is that a following shouldn't be the trust signal.
- **A single composite "trust score"** as a tracked internal metric that quietly becomes a de facto ranking mechanism even if it's never shown to users — if it's not a UI feature (see ADR-007 in [decisions.md](../decisions.md)), it shouldn't be a shadow metric either, since a metric the team optimizes toward tends to leak into product decisions even unshown.
