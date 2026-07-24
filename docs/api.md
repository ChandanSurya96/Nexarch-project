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
```

### Broker Connections
```
POST   /api/v1/broker-connections/init            { broker_name } → { redirect_url }
POST   /api/v1/broker-connections/callback        { broker_name, auth_code }
GET    /api/v1/broker-connections
DELETE /api/v1/broker-connections/:id
POST   /api/v1/broker-connections/:id/sync        # manual "sync now", rate-limited
```

### Portfolios & Holdings
```
GET    /api/v1/portfolios/:id
GET    /api/v1/portfolios/:id/holdings
GET    /api/v1/portfolios/:id/analytics           # allocation, sector split, health metrics
GET    /api/v1/portfolios/:id/history             # snapshots over time
PATCH  /api/v1/portfolios/:id                     # e.g. toggle is_public
```

### Discovery
```
GET    /api/v1/discovery/investors                # filterable, paginated feed
GET    /api/v1/discovery/strategy-categories
```

### Public Investor Library
```
GET    /api/v1/public-investors
GET    /api/v1/public-investors/:slug
```

### Follows
```
POST   /api/v1/portfolios/:id/follow
DELETE /api/v1/portfolios/:id/follow
GET    /api/v1/users/me/following
```

## Example: Portfolio Detail Response

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
      "holding_count": 14
    },
    "as_of": "2026-07-13"
  },
  "meta": {},
  "error": null
}
```

`diversification_score` and `sector_concentration_hhi` are computed directly from current holdings composition (see [database.md](./database.md), [product-requirements.md](./product-requirements.md)). Fields like true return volatility are intentionally absent here until a market-data dependency is resolved — see ADR-008 in [decisions.md](./decisions.md).

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
