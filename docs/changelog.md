# Changelog

**Purpose:** Chronological record of major features, architectural changes, and releases. Format follows [Keep a Changelog](https://keepachangelog.com) conventions. See [decisions.md](./decisions.md) for the *reasoning* behind entries here — this file is the *what and when*, that one is the *why*.

---

## [Unreleased]

Nothing pending beyond what's logged below — this section stays as the running head for whatever's currently in progress.

---

## [2026-07-25] — Milestone 2: Broker Connection, Sync & Analytics

### Added
- Upstox adapter (`app/integrations/broker/`) implementing the shared `BrokerAdapter` interface — login URL, auth-code exchange, holdings fetch — plus a `registry.py` lookup so adding a second broker is additive (see [roadmap.md](./roadmap.md)).
- Envelope encryption for broker tokens (`app/services/encryption_service.py`) — see ADR-014 in [decisions.md](./decisions.md) for why this is a KMS stand-in, not yet production-ready.
- Static sector/market-cap enrichment reference (`app/data/sector_mapping.py`) — see ADR-013.
- Holdings normalization (`app/services/normalization_service.py`) and portfolio analytics (`app/services/analytics_service.py`: sector/asset allocation, HHI concentration, diversification score, portfolio age, no composite score per ADR-007, no volatility field per ADR-008).
- Celery sync worker (`app/celery_app.py`, `app/tasks/sync.py`, `app/services/sync_service.py`) — initial sync queued on connect, daily scheduled sync via Celery Beat, distinct handling for expired-token vs. generic failures per [broker-integrations.md](./broker-integrations.md).
- `audit_logs` table (migration `0002`) and `app/services/audit_service.py` — wired into broker connect/disconnect/sync/error **and** retrofitted onto Milestone 1's login/refresh endpoints, closing a gap that predates this milestone (security.md's event_type enum already specified `login`/`token_refresh`).
- New endpoints: `POST/GET/DELETE /api/v1/broker-connections`, `POST /api/v1/broker-connections/:id/sync`, `GET /api/v1/portfolios/:id`, `GET /api/v1/portfolios/:id/holdings`, `GET /api/v1/portfolios/:id/analytics`, `PATCH /api/v1/portfolios/:id`.
- 66 new pytest tests (86 total) covering encryption round-trip/tamper detection, the Upstox adapter (fully mocked, no live credentials), normalization, analytics math, and both new endpoint groups.

### Fixed
- `create_app()` imported `app.config` at module level, before `load_dotenv()` ever ran — `Config`'s class attributes (e.g. `SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "")`) bake in at class-definition time, so this silently resolved to an empty string on any entry point that didn't pre-populate the environment itself. `TestingConfig`'s sqlite default masked this for the pytest suite; it surfaced when `app/celery_app.py` became the first code path to call bare `create_app()` without that workaround. Fixed by deferring the `app.config` import to inside `create_app()`, after `load_dotenv()`.

### Notes
- Scope was deliberately limited to broker-connect → sync → analytics (backend only). Discovery feed, Public Investor Library, follows, the frontend, a second broker, and Account Aggregator integration are explicitly out of scope for this milestone — see [decisions.md](./decisions.md) and [product/feature-backlog.md](./product/feature-backlog.md) for what's next.

---

## [2026-07-21] — Milestone 1: Auth & Schema Foundation

### Added
- Flask app factory + blueprint structure (`auth`, `users`), routes → services → models layering per [architecture.md](./architecture.md).
- Initial schema migration (`0001`): `users`, `broker_connections`, `portfolios`, `holdings`, `portfolio_snapshots`, with the ADR-006 owner-invariant check constraint and all indexes from [database.md](./database.md).
- JWT auth: register/login/refresh/logout, bcrypt password hashing, short-lived access token + rotating httpOnly refresh cookie per ADR-004.
- 20 passing pytest tests plus a standalone smoke-test script.

---

## [2026-07-14] — Phase 0: Documentation & Architecture

### Added
- Initial `/docs` knowledge base created: README, vision, roadmap, architecture, database, api, broker-integrations, design-system, security, development-guide, product-requirements, decisions, changelog, and the `/docs/product` subfolder (user-personas, user-journey, feature-backlog, competitor-analysis, market-research, monetization, go-to-market, success-metrics, user-feedback).
- Database schema designed (not yet migrated/implemented).
- API contract designed (not yet implemented).
- Broker/Account Aggregator integration strategy researched and documented, including two open risks requiring founder/legal attention before public launch (see [decisions.md](./decisions.md) ADR-010, ADR-011).

### Notes
- No application code had been written at this point. Per the founding process, this was intentional — Phase 1 implementation began after founder review of this documentation set (see Milestone 1 above). See [roadmap.md](./roadmap.md).

---

## Template for Future Entries

```
## [Version or Date] — Short Description

### Added
- New features

### Changed
- Changes to existing functionality

### Fixed
- Bug fixes

### Deprecated
- Soon-to-be-removed features

### Removed
- Removed features

### Security
- Vulnerability fixes, dependency updates with security relevance
```
