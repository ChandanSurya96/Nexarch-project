# API

**Purpose:** REST conventions, endpoint structure, auth flow, and response formats for the Nexarch backend. Frontend and backend should treat this as the contract between them — if an endpoint's actual behavior differs from this document, that's a bug in one of the two, not a reason to just adapt silently. See [architecture.md](./architecture.md) for the system this sits inside, and [security.md](./security.md) for the auth model in depth.

---

## Conventions

- **Base path:** `/api/v1/` — versioned from day one so a breaking v2 doesn't require a big-bang migration later.
- **Resources:** plural nouns, resource-based URLs (`/portfolios/:id/holdings`, not `/getHoldings`).
- **Format:** JSON in, JSON out. `Content-Type: application/json`.
- **Auth:** `Authorization: Bearer <access_token>` on every authenticated request.

## Response Envelope

```json
{
  "data": { },
  "meta": { },
  "error": null
}
```

Errors use the same envelope with `data: null` and a populated `error`:

```json
{
  "data": null,
  "meta": {},
  "error": {
    "code": "BROKER_CONNECTION_EXPIRED",
    "message": "This broker connection needs to be reconnected.",
    "status": 401
  }
}
```

Error `code` values are stable, machine-readable strings (`UPPER_SNAKE_CASE`) the frontend can switch on; `message` is for humans and may change wording without being a breaking change.

## Pagination

Offset-based for MVP simplicity (cursor-based is a Phase 2+ upgrade if discovery-feed scale demands it):

```
GET /api/v1/discovery/investors?page=1&per_page=20
```

```json
{
  "data": [ ... ],
  "meta": {
    "pagination": { "page": 1, "per_page": 20, "total": 483, "total_pages": 25 }
  }
}
```

## Authentication Flow

```
POST /api/v1/auth/register        { email, password, username }
POST /api/v1/auth/login           { email, password } → { access_token }
                                   (+ refresh_token set as an httpOnly cookie, not in the body)
POST /api/v1/auth/refresh         (reads refresh_token from the httpOnly cookie) → { access_token }
                                   (rotates the cookie on success)
POST /api/v1/auth/logout          (clears the refresh cookie)
```

Access tokens are short-lived (15 min); refresh tokens are longer-lived and stored as httpOnly secure cookies, not in frontend JS-accessible storage. Full reasoning in [security.md](./security.md).

## Core Endpoint Groups

### Users & Profiles
```
GET    /api/v1/users/me
PATCH  /api/v1/users/me
GET    /api/v1/users/:username            # public profile
GET    /api/v1/users/me/portfolio         # the caller's own portfolio, or null
```

`/users/me/portfolio` exists because every portfolio endpoint is keyed by `portfolio_id`, and there's no other way for the frontend to discover the signed-in user's own id. It returns the same shape as the Portfolio Detail Response below — or `data: null` (200, not a 404) when the user has no portfolio yet. That's a normal, expected state, not an error: a `Portfolio` row is only created lazily on a broker connection's first successful sync (see [broker-integrations.md](./broker-integrations.md)), so every new signup — and even a user who just finished connecting a broker seconds ago — legitimately has none for a little while. See ADR-019 in [decisions.md](./decisions.md).

### Broker Connections
```
POST   /api/v1/broker-connections/init            { broker_name } → { redirect_url }
POST   /api/v1/broker-connections/callback        { broker_name, auth_code, state }
GET    /api/v1/broker-connections
DELETE /api/v1/broker-connections/:id
POST   /api/v1/broker-connections/:id/sync        # manual "sync now", rate-limited
```

### Portfolios & Holdings
```
GET    /api/v1/portfolios/:id
GET    /api/v1/portfolios/:id/holdings
GET    /api/v1/portfolios/:id/analytics           # allocation, sector split, health metrics, strategy overview
GET    /api/v1/portfolios/:id/activity            # descriptive diffs between consecutive syncs (ADR-015, Milestone 3)
GET    /api/v1/portfolios/:id/profile             # detail + holdings + analytics + activity combined
GET    /api/v1/portfolios/:id/history             # raw snapshot history over time (Milestone 5)
GET    /api/v1/portfolios/compare?ids=<uuid>,<uuid> # side-by-side comparison of two portfolios + diff (Milestone 6)
PATCH  /api/v1/portfolios/:id                     # e.g. toggle is_public
```

`/profile` is additive, not a replacement — it exists for a single profile-page fetch, wrapping the same four sections the separate endpoints already return:
```json
GET /api/v1/portfolios/9f2c.../profile

{
  "data": {
    "portfolio": { "id": "9f2c...", "portfolio_type": "verified", "is_public": true, "display_name": "...", "strategy_tags": [...], "created_at": "...", "updated_at": "..." },
    "holdings": [ { "id": "...", "symbol": "...", ... } ],
    "analytics": { "portfolio_id": "9f2c...", "total_value": 1245000, "sector_allocation": {...}, "health": {...}, "strategy_overview": "...", "as_of": "2026-07-13" },
    "activity": [ { "from_date": "...", "to_date": "...", "sector_changes": [...], "holding_count_change": null, "summary": "..." } ]
  },
  "meta": {},
  "error": null
}
```
Powered by `app/services/portfolio_profile_service.py`, which coordinates `analytics_service`, `activity_service`, and `strategy_overview_service` — the separate endpoints call the same underlying pieces, so the two paths can never disagree with each other.

### Discovery
```
GET    /api/v1/discovery/investors                # filterable, paginated feed
GET    /api/v1/discovery/strategy-categories
```
Each item in `/discovery/investors` is the same shape as the Portfolio Detail Response below, plus a `health` field (the latest synced health metrics, or `null`) — see the note there on why the shapes are kept identical rather than maintained separately.

### Public Investor Library
```
GET    /api/v1/public-investors
GET    /api/v1/public-investors/:slug
```
Each entry includes `portfolio_id` (added Milestone 4c, ADR-022 in [decisions.md](./decisions.md)) — the linked `Portfolio`'s id, for navigating to its full holdings/allocation/health view at the Portfolio Detail Response shape below. `null` only if a `PublicInvestor` record has been created but not yet linked to a seeded portfolio, which shouldn't happen past the seed script (`scripts/seed_public_investors.py`) running.

### Follows
```
POST   /api/v1/portfolios/:id/follow
DELETE /api/v1/portfolios/:id/follow
GET    /api/v1/users/me/following
```

## Example: Portfolio Detail Response

```json
GET /api/v1/portfolios/9f2c...

{
  "data": {
    "id": "9f2c...",
    "portfolio_type": "verified",
    "is_public": true,
    "display_name": "Rohan Mehta",
    "strategy_tags": ["long-term", "value"],
    "created_at": "2026-01-15T09:00:00+00:00",
    "updated_at": "2026-07-25T02:00:00+00:00"
  },
  "meta": {},
  "error": null
}
```

`display_name` and `strategy_tags` (added when the discovery feed/follows/portfolio-detail contracts were stabilized ahead of Milestone 4) resolve identically everywhere a portfolio is serialized — the discovery feed, `GET /users/me/following`, and this detail endpoint all use the same underlying resolution (`app/services/portfolio_service.py`), so a portfolio never describes itself differently depending on which list it was reached from. `display_name` is the public investor's name for Public Investor Library entries, or the owning user's display name/username for verified portfolios.

## Example: Portfolio Analytics Response

```json
GET /api/v1/portfolios/9f2c.../analytics

{
  "data": {
    "portfolio_id": "9f2c...",
    "total_value": 1245000,
    "sector_allocation": { "Financials": 0.31, "IT": 0.24, "Consumer": 0.18, "Other": 0.27 },
    "health": {
      "diversification_score": 0.72,
      "sector_concentration_hhi": 0.19,
      "portfolio_age_days": 612,
      "holding_count": 14,
      "volatility": 0.132,
      "momentum": 0.086
    },
    "strategy_overview": "Currently weighted toward Financials (31% of synced holdings), with exposure spread across other sectors as well, predominantly in large-cap holdings.",
    "as_of": "2026-07-13",
    "strategy_categorization": [
      {
        "slug": "low-risk",
        "name": "Low-risk",
        "explanation": "Annualized volatility of 13.2% is at or below the 15% threshold for lower-than-typical broad-market equity risk."
      }
    ]
  },
  "meta": {},
  "error": null
}
```

`diversification_score` and `sector_concentration_hhi` are computed directly from current holdings composition (see [database.md](./database.md), [product-requirements.md](./product-requirements.md)). `volatility` (added Milestone 5, ADR-024 resolving ADR-008) is annualized, value-weighted across holdings, computed from the broker's own historical price data — `null` wherever there isn't a broker connection to fetch price history from (e.g. Public Investor Library portfolios) or too few data points to compute it honestly. `momentum` (added Milestone 7, ADR-028) is a trailing ~90-day value-weighted return, computed from the same historical price data as volatility — same nullability rules. `strategy_overview` (added Milestone 3) is the rules-based Investor Strategy Overview from [product-requirements.md](./product-requirements.md) — descriptive-only wording, never a recommendation (see [security.md](./security.md)); `null` when there's not yet enough synced data to describe. `strategy_categorization` (added Milestone 7, ADR-028) lists which of the 8 fixed strategy categories currently apply to this portfolio, each with a plain-language explanation citing the observed number against its threshold — computed fresh from the current snapshot's `health` and holdings, not stored; always `[]` for Public Investor Library portfolios (whose tags are manually curated, not rule-derived) and for portfolios with no snapshot yet. Only 3 of the platform's 8 fixed categories can appear here (Small-cap Specialist, Low-risk, Momentum) — the rest are deferred pending real data sources, see ADR-028.

## Example: Portfolio Activity Response

```json
GET /api/v1/portfolios/9f2c.../activity

{
  "data": [
    {
      "from_date": "2026-07-18",
      "to_date": "2026-07-25",
      "sector_changes": [
        { "sector": "Financials", "before": 0.31, "after": 0.28 },
        { "sector": "IT", "before": 0.24, "after": 0.27 }
      ],
      "holding_count_change": null,
      "summary": "Between 2026-07-18 and 2026-07-25, sector allocation shifted: Financials 31%→28%, IT 24%→27%."
    }
  ],
  "meta": {},
  "error": null
}
```

Computed on read by diffing consecutive `portfolio_snapshots` rows — see ADR-015 in [decisions.md](./decisions.md). Strictly descriptive: no attributed cause, no "auto-copy" language, no comments. Empty list until a portfolio has 2+ snapshots.

## Example: Portfolio History Response

```json
GET /api/v1/portfolios/9f2c.../history

{
  "data": [
    {
      "snapshot_date": "2026-07-18",
      "total_value": 1200000,
      "diversification_score": 0.70,
      "volatility": null
    },
    {
      "snapshot_date": "2026-07-25",
      "total_value": 1245000,
      "diversification_score": 0.72,
      "volatility": 0.182
    }
  ],
  "meta": {},
  "error": null
}
```

Added Milestone 5 — documented since Phase 0 but not built until now. Raw snapshot-level data, oldest to newest, distinct from `.../activity`'s descriptive diffs over the same `portfolio_snapshots` table (this is the data; that's the narration). `volatility` is `null` for any snapshot recorded before ADR-024 shipped, or wherever it couldn't be honestly computed — same convention as everywhere else. Empty list until a portfolio has at least one snapshot.

`snapshot_date` isn't unique — more than one sync can land on the same calendar date, and each produces its own entry here (see ADR-025). Ordering (both this list and which snapshot `.../analytics` treats as current) is by `snapshot_date` and then by an internal creation-order tiebreaker, so entries sharing a date still appear in the order they actually happened, not arbitrarily.

## Example: Portfolio Comparison Response

```json
GET /api/v1/portfolios/compare?ids=9f2c...,3af1...

{
  "data": {
    "portfolios": [
      { "portfolio": { "id": "9f2c...", "display_name": "...", ... }, "analytics": { "total_value": 850000, "sector_allocation": {"Financials": 0.55, "IT": 0.25, "Consumer": 0.2}, "health": {"diversification_score": 0.6, "sector_concentration_hhi": 0.4, "portfolio_age_days": 400, "holding_count": 8, "volatility": 0.16}, "strategy_overview": "...", "as_of": "2026-07-25" } },
      { "portfolio": { "id": "3af1...", "display_name": "...", ... }, "analytics": { "total_value": 1250000, "sector_allocation": {"IT": 0.6, "Pharma": 0.4}, "health": {"diversification_score": 0.48, "sector_concentration_hhi": 0.52, "portfolio_age_days": 400, "holding_count": 5, "volatility": 0.27}, "strategy_overview": "...", "as_of": "2026-07-25" } }
    ],
    "diff": {
      "total_value": { "a": 850000, "b": 1250000, "delta": 400000 },
      "sector_allocation": {
        "Financials": { "a": 0.55, "b": 0.0, "delta": -0.55 },
        "IT": { "a": 0.25, "b": 0.6, "delta": 0.35 },
        "Consumer": { "a": 0.2, "b": 0.0, "delta": -0.2 },
        "Pharma": { "a": 0.0, "b": 0.4, "delta": 0.4 }
      },
      "health": {
        "diversification_score": { "a": 0.6, "b": 0.48, "delta": -0.12 },
        "sector_concentration_hhi": { "a": 0.4, "b": 0.52, "delta": 0.12 },
        "portfolio_age_days": { "a": 400, "b": 400, "delta": 0 },
        "holding_count": { "a": 8, "b": 5, "delta": -3 },
        "volatility": { "a": 0.16, "b": 0.27, "delta": 0.11 }
      }
    }
  },
  "meta": {},
  "error": null
}
```

Added Milestone 6 (ADR-026). `portfolios[0]` corresponds to the first id in `ids`, `portfolios[1]` to the second; every `delta` in `diff` is `b - a` (second id's value minus the first's) — the sign always points the same direction the ids were supplied in, not toward whichever side is "better" (there's no such ranking here, per ADR-007). `delta` is `null` wherever either side's value couldn't be honestly computed — no snapshot yet, or (for `sector_allocation`) one side has no snapshot at all — same convention as `volatility` elsewhere in this API; a sector missing from one side's *real* snapshot is a genuine `0.0`, not `null`. Comparing a portfolio to itself is rejected (`400 CANNOT_COMPARE_SAME_PORTFOLIO`); visibility follows the same rules as every other portfolio endpoint (`404 PORTFOLIO_NOT_FOUND` for a nonexistent or private-to-you portfolio).

## Rate Limiting

Standard headers on every response:
```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 87
X-RateLimit-Reset: 1752480000
```
Applied per-user for authenticated endpoints, per-IP for public/unauthenticated ones (discovery feed, public investor pages). The `broker-connections/:id/sync` endpoint has its own tighter limit independent of general API rate limits, since it triggers a real outbound call to a third-party broker API that has its own limits — see [broker-integrations.md](./broker-integrations.md).

## Versioning

Breaking changes get a new version prefix (`/api/v2/`); additive changes (new optional fields, new endpoints) don't require a version bump. The old version is supported for a defined deprecation window, not removed the day v2 ships.

## GraphQL — Not Now

REST is sufficient for MVP's access patterns (a handful of well-known views: profile, portfolio, discovery feed). GraphQL would add real value once the frontend needs to compose many different partial views of the same data flexibly — that's not the Phase 1 problem. Revisit only if a concrete pain point shows up, not speculatively.
