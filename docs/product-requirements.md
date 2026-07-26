# Product Requirements

**Purpose:** Feature-by-feature breakdown with acceptance criteria and the business logic behind each. This is the bridge between [vision.md](./vision.md) (why) and [database.md](./database.md)/[api.md](./api.md) (how). See [product/user-personas.md](./product/user-personas.md) and [product/user-journey.md](./product/user-journey.md) for the people and flows this serves.

---

## Feature: Broker Connection

**What it does:** lets a user securely connect a supported brokerage account (or Account Aggregator consent flow) to generate verified holdings.

**Acceptance criteria:**
- Given a user on their profile page, when they click "Connect Broker," then they see the list of currently supported brokers with accurate status (some may show "coming soon").
- Given a user completes a broker's auth flow, when the callback returns successfully, then a `broker_connections` record is created with `status: active` and an initial sync is queued within seconds, not left for the next scheduled run.
- Given a broker connection's token has expired, when the next scheduled sync runs, then the connection is marked `status: expired` and the user sees a clear "reconnect" prompt — not a silent failure and not a generic error.
- Given a user disconnects a broker, when the disconnect completes, then the stored token is deleted (not just deactivated) and previously synced holdings are either removed or clearly marked as stale, per the user's choice.

## Feature: Verified Portfolio Profile

**What it does:** automatically generates a public (if the user opts in) profile from synced holdings.

**Acceptance criteria:**
- Given a user has at least one active broker connection with a completed sync, when they view their profile, then it shows a verification badge, current holdings, sector/asset allocation, and portfolio-health metrics.
- Given a user has not made their profile public, when another user searches for them, then the profile does not appear in discovery or public search — private by default is the correct default, not an afterthought toggle.
- The verification badge's tooltip/explanation text must state exactly what verification means (data came from an authenticated broker connection) and exactly what it doesn't mean (not investment advice, not a guarantee of skill or returns) — this copy requirement isn't optional polish, see [security.md](./security.md).

## Feature: Investor Discovery Feed

**What it does:** lets users browse verified and public investors by strategy, diversification, and other objective characteristics — the core "browse people, not stocks" experience from [vision.md](./vision.md).

**Acceptance criteria:**
- Filters (Long-term, Growth, Value, Dividend, Momentum, ETF, Small-cap Specialist, Low-risk) are applied via the many-to-many `strategy_categories` relationship (see [database.md](./database.md)), and a portfolio can match more than one filter.
- Results are paginated (see [api.md](./api.md)) and support at minimum: recency of last sync, portfolio age, and alphabetical sort — "most followed" sort is a Phase 2+ addition once follow counts are meaningful at scale, to avoid a cold-start feed that only ever surfaces the same handful of early profiles.
- The feed must clearly visually distinguish Verified (broker-synced) profiles from Public Investor Library entries — they carry different evidentiary weight and should never look identical.

## Feature: Portfolio Analytics

**What it does:** computes and displays allocation, sector distribution, diversification, concentration, and historical change.

**Acceptance criteria and calculation notes:**
- **Sector/asset allocation:** straightforward percentage breakdown of current holdings by value.
- **Diversification / sector concentration:** computed via the Herfindahl-Hirschman Index (HHI) of sector weights — sum of squared sector percentages. A single-sector portfolio scores 1.0 (maximally concentrated); an evenly spread portfolio across many sectors approaches 0. This is directly computable from current holdings alone, with no external dependency.
- **Volatility / true risk metrics:** **not available from holdings-snapshot data alone.** Computing real volatility requires historical price series for each holding, which broker read-only sync doesn't provide — it gives current holdings, not tick-level or even daily price history. This is deferred pending a market-data vendor decision (see ADR-008 in [decisions.md](./decisions.md)), and the UI must not imply a volatility figure exists before it genuinely does — a fabricated-looking number is worse than an honestly missing one on a trust-first product.
- **Portfolio age:** derived from `portfolio_snapshots` history, not from `broker_connections.connected_at` alone (a user may have held a security for years before connecting Nexarch — see [product/user-journey.md](./product/user-journey.md) for why this distinction matters to the persona it affects most).

## Feature: Portfolio Health

**What it does:** presents objective indicators (diversification, concentration, portfolio age, holding consistency, risk level) instead of one subjective trust score.

**Why no single score, explicitly:** a single number invites exactly the kind of "just trust this" shortcut Nexarch exists to replace, and — per [security.md](./security.md) — is a much shorter step from "descriptive data" to "advice" than a set of labeled, individually-understandable indicators. Each indicator should be independently explained (a tooltip or linked explainer), not just displayed as a number.

## Feature: Investor Strategy Overview

**What it does:** a short, plain-language summary of a portfolio's apparent approach (e.g., "Focuses on long-term compounders with diversified exposure across technology, financials, and consumer sectors.").

**Acceptance criteria:**
- Copy must be generated/reviewed to describe **observed historical composition and behavior**, never framed as a recommendation ("you should hold these sectors") or a promise ("this strategy delivers strong returns"). See [security.md](./security.md) — this is the single feature most likely to be read as advice if the copy isn't deliberately descriptive.
- For Phase 1, this can be a rules-based summary (e.g., templated off sector concentration + turnover + market-cap mix); Phase 3's AI-generated version must follow the same descriptive-only constraint, not a looser one, since a model is more likely to slip into advisory-sounding language by default if not explicitly constrained.

## Feature: Public Investor Library

**What it does:** educational profiles of well-known Indian investors (Radhakishan Damani, Ashish Kacholia, Vijay Kedia, Dolly Khanna, Mukul Agrawal, and others over time), built from public regulatory shareholding disclosures.

**Acceptance criteria:**
- Every entry must be clearly labeled "Public Portfolio" and visually distinct from a Verified (broker-synced) profile — see Discovery Feed criteria above.
- Every holding shown must trace to a specific, dated, cited public disclosure (`source_disclosure_url` + `last_disclosure_update` in [database.md](./database.md)) — never estimated, interpolated, or inferred between disclosure dates.
- Data refresh process for Phase 1 is manual/curated (there's no reliable public API for shareholding-pattern disclosures at this time); this is logged as an explicit operational dependency, not hidden inside "the data updates automatically" language anywhere in the UI.
- Profile copy must not imply endorsement by the named individual — these are educational reconstructions from public filings, not accounts the individual operates or has reviewed.

## Feature: Following

**What it does:** lets a user follow a portfolio (verified or public) to track it, without any capital or execution relationship — a deliberate contrast with copy-trading models like the US app Dub (see [product/competitor-analysis.md](./product/competitor-analysis.md)), where "follow" moves real money.

**Acceptance criteria:**
- Following a portfolio never moves money or places any order — this is worth stating as an explicit acceptance criterion precisely because it's the single most common expectation a user might arrive with from other "social investing" products.

## Feature: Portfolio Comparison

**What it does:** shows two portfolios' analytics and health metrics side by side, with a computed diff, so a user can see how their own portfolio (or any two portfolios they can view) differ objectively.

**Acceptance criteria:**
- Given two portfolios the requester can view, when they're compared, then both portfolios' current holdings-derived analytics (total value, sector allocation, health metrics) are shown side by side, plus a per-field diff.
- Given one or both portfolios have no synced snapshot yet, then the comparison renders those fields honestly empty (`null`/"not enough data"), never a fabricated zero or invented delta — the same convention as every other nullable field in this API (ADR-008/ADR-024). This applies at the per-sector level too: a sector present in one portfolio but entirely absent because the other side has no snapshot at all is "unknown," not "confirmed 0%."
- Given the same portfolio id supplied twice, then the comparison is rejected with a clear error rather than silently diffing a portfolio against itself.
- Visibility rules are unchanged: a private portfolio is exactly as invisible to a non-owner in a comparison as anywhere else in the API (same 404, per `get_visible_portfolio`) — comparison introduces no new access path.
- No composite "who wins" score or ranking is computed or displayed — each metric is shown and diffed independently, consistent with ADR-007's no-single-trust-score rule. A higher value on one metric (e.g. concentration/HHI) is not framed as "better" or "worse."
- Milestone 6 ships contextual entry points only (e.g. "Compare with mine" from an investor's card or portfolio page) — not a standalone portfolio picker (ADR-027). Direct navigation without two portfolios selected shows a guided empty state, not an error.

## Non-Functional Requirements

- Portfolio page load: target under 2s for a returning visitor (cached analytics), under 5s for a fresh sync-triggered load.
- Sync reliability: target >95% successful scheduled syncs per connected portfolio per day, with clear surfacing of the failing 5% rather than silent retries indefinitely.
- Availability target for Phase 1: standard single-region uptime, no multi-region requirement yet — premature for current scale.
