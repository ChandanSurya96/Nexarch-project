# Changelog

**Purpose:** Chronological record of major features, architectural changes, and releases. Format follows [Keep a Changelog](https://keepachangelog.com) conventions. See [decisions.md](./decisions.md) for the *reasoning* behind entries here — this file is the *what and when*, that one is the *why*.

---

## [Unreleased]

Nothing pending beyond what's logged below — this section stays as the running head for whatever's currently in progress.

---

## [2026-07-25] — Phase 1 cleanup: OAuth state validation + self-follow fix

### Added
- OAuth `state` parameter (ADR-023) on the broker connect flow: `init_connection` generates and stores a single-use token in Redis; `handle_callback` verifies and consumes it, rejecting a missing/wrong/reused/wrong-user state as `INVALID_OAUTH_STATE`. `BrokerAdapter.get_login_url` and `UpstoxAdapter` updated; `app/broker-callback/page.tsx` now reads `state` from the broker's redirect alongside `code`. `smoke_test.py` updated to match (still no live Redis/broker needed).
- `follow_service.follow()` now rejects following your own portfolio (`CANNOT_FOLLOW_OWN_PORTFOLIO`) — found reachable via the new Discovery Feed, which lists a user's own portfolio in the same grid as everyone else's. `InvestorCard` gained an `isOwnPortfolio` prop; `app/discover/page.tsx` hides the Follow button on the viewer's own card.

### Fixed
- Wiring the self-follow fix into `app/discover/page.tsx` (a page not gated by `RequireAuth`, since it's meant to be browsable while signed out) surfaced a real race: `useMyPortfolio()` fired on mount unconditionally, sometimes before `AuthProvider`'s silent-refresh-on-mount had set the in-memory access token, getting a 401 back. `/profile` never hit this because `RequireAuth` doesn't mount its children until auth resolves. Fixed by adding an `enabled` option to `useMyPortfolio`, gated on `!!user` on pages (like Discover) that render for signed-out visitors too.

### Notes
- Both fixes were originally spawned as background tasks in isolated worktrees; those worktrees turned out to predate all of this session's code (created before Milestone 2 was ever committed) and couldn't have produced a usable result. Implemented directly here instead.

---

## [2026-07-25] — Milestone 4c: Discovery Feed + Public Investor Library

### Added
- `portfolio_id` added to `PublicInvestorSchema` (ADR-022) so library entries can link to their profile view; eager-loaded to avoid N+1.
- `components/ui/Pagination.tsx`, `components/Nav.tsx` (wired into `app/layout.tsx` — the first way to actually reach these pages without typing a URL), `components/portfolio/InvestorCard.tsx` (shared list-item summary for both surfaces, with an inline Follow/Unfollow button).
- `lib/hooks/useDiscoveryFeed`, `useStrategyCategories`, `usePublicInvestors`.
- `apiFetchWithMeta` added to `lib/api.ts` (additive — `apiFetch` unchanged) so callers that need pagination `meta`, not just `data`, have a way to get it.
- `app/discover/page.tsx` — strategy filter chips, sort select (recency/portfolio age/alphabetical), paginated card grid.
- `app/library/page.tsx` — Public Investor Library card grid (unpaginated — the endpoint returns the full list).
- `app/page.tsx` simplified now that `Nav` carries auth actions — links to Discover/Library as the primary CTAs instead.
- 7 new frontend tests: `Pagination`'s boundary behavior, `useDiscoveryFeed`'s query-param construction and response mapping.

### Notes
- Manually verified: strategy filtering, sort, and pagination against the 5 seeded Public Investor Library entries plus the verified test portfolio seeded for Milestone 4b's manual checks; confirmed Verified vs. Public Portfolio badges are visually distinct in both views; confirmed inline Follow/Unfollow from a card; checked the grid at a narrow viewport per `design-system.md`'s explicit mobile-first callout for this page.
- Phase 1's roadmap.md exit criteria (signup → verified profile → browse) is now fully built end to end, closing out Milestone 4.

---

## [2026-07-25] — Milestone 4b: Verified Profile Page + Broker Connection Flow

### Added
- `GET /api/v1/users/me/portfolio` (ADR-019) — lets the frontend discover the signed-in user's own portfolio id; returns `data: null` (not a 404) when none exists yet.
- Remaining `docs/design-system.md` components: `Badge`, `Avatar`, `StatCard`, `HoldingsTable` (sortable, tabular-nums), `AllocationChart` (Recharts donut with a visually-hidden accessible data table alongside it), `Modal`.
- `components/portfolio/PortfolioProfileView.tsx` — the shared rendering component (holdings, sector allocation, health stat grid, strategy overview, activity) reused by both the owner and viewer routes.
- `app/profile/page.tsx` — the signed-in user's own portfolio: Connect Broker CTA, syncing/expired/ready states, manual "Sync now", public/private toggle and broker disconnect (both behind a `Modal` confirm).
- `app/broker-callback/page.tsx` — completes the OAuth round-trip after the broker redirects back, waiting for the silent-refresh-restored session before calling the callback endpoint (a full browser navigation away and back tears down and reloads the app's JS, so the in-memory access token is gone until then).
- `app/portfolios/[id]/page.tsx` — read-only viewer for any portfolio (verified or Public Investor Library — both are just `Portfolio` rows per ADR-006), with a Follow/Unfollow button.
- `lib/hooks/` — React Query wrappers for the above: `useMyPortfolio` (bounded polling per ADR-020), `usePortfolioProfile`, `useBrokerConnections`, `useFollowingIds`, and mutations for init/disconnect/sync-now/visibility/follow.
- Recharts added as a dependency (first real use, named in `design-system.md` since Phase 0).
- 15 new frontend tests (Vitest): `useMyPortfolio`'s polling behavior, the broker-callback page's success/error/session-expired paths, `useUpdateVisibility`'s mutation.

### Fixed
- `broker_connection_service.handle_callback` unconditionally inserted a new `BrokerConnection` row on every callback — reconnecting after an expired token would leave the old row orphaned and, on the new row's first sync, create a *second*, disconnected `Portfolio` for a user who already had one (ADR-021). Found while building the frontend's Reconnect flow, before it shipped on top of it. Fixed by looking up an existing `(user_id, broker_name)` connection and updating it in place; regression-tested.

### Notes
- A real Upstox OAuth round-trip can't be completed in this environment (no live broker credentials) — manual verification covered what's reachable (Connect Broker calling `/init`, the callback page's error handling) plus the full profile rendering against a directly-seeded test portfolio (holdings/snapshot rows inserted the same way the backend's own tests simulate a completed sync).
- Discovery Feed and Public Investor Library pages remain Milestone 4c — this milestone only built the profile view they'll eventually link to.

---

## [2026-07-25] — Milestone 4a: Frontend Foundation + Auth

### Added
- Tailwind wired up end to end: `postcss.config.js`, `tailwind.config.ts` mapping the color tokens from [design-system.md](./design-system.md) into class names (`bg-surface`, `text-primary`, `accent`, etc.), `styles/globals.css` defining the underlying CSS custom properties. Dark mode only for this milestone — no light/dark toggle yet.
- Inter font via `next/font/google`, wired into `app/layout.tsx`.
- Base UI components (`components/ui/`): `Button` (primary/secondary/ghost), `Card`, `EmptyState` — only what login/register/the shell need; the rest of [design-system.md](./design-system.md)'s component list (`Badge`, `HoldingsTable`, `AllocationChart`, `StatCard`, `Avatar`, `Modal`) is deferred to Milestone 4b/4c.
- `lib/auth/AuthProvider.tsx` + `useAuth()`: silent-refresh-on-mount, `login`/`register`/`logout`, access token held in React state and synced to `lib/api.ts` (ADR-017) — never `localStorage`.
- `app/providers.tsx`: `QueryClientProvider` (first real use of the already-installed `@tanstack/react-query`, ADR-009) wrapping `AuthProvider`.
- `components/RequireAuth.tsx`: client-side route guard reading the same auth state (ADR-018).
- `app/login/page.tsx`, `app/register/page.tsx`; `app/page.tsx` now shows a real signed-in/signed-out state instead of Milestone 1's placeholder text.
- Vitest + React Testing Library set up (`vitest.config.ts`, `vitest.setup.ts`); 6 new tests covering `AuthProvider`'s silent-refresh success/failure paths and login-page submission/error/validation behavior.

### Fixed
- `lib/api.ts`'s `apiFetch` defaulted to the *absolute* backend URL, bypassing the `rewrites()` proxy `next.config.ts` already had for exactly this purpose — a cross-origin request from the browser that Flask has no CORS configuration to allow. Fixed per ADR-016 to always call the relative `/api/v1` path.
- That fix then exposed a second, previously-latent bug: the rewrite's `source: "/api/:path*"` doubled the path once something actually used it (`/api/v1/v1/auth/refresh`, a live 404), because `NEXT_PUBLIC_API_BASE_URL` already ends in `/api/v1`. Fixed by pinning the rewrite source to `/api/v1/:path*`. Caught by manually driving the register → login → hard-refresh flow in a browser, not by type-check or the unit test suite — see ADR-016 for the detail.

### Notes
- Scope was deliberately the foundation only: design tokens, the API/auth layer, and login/register as the end-to-end proof. The verified profile page, discovery feed, and Public Investor Library pages are Milestone 4b/4c, built on top of this — see [product/feature-backlog.md](./product/feature-backlog.md).
- Manually verified against the live local stack (Postgres/Redis/Flask/Next dev server): register → auto-login → hard refresh (session restored via silent refresh, no bounce to `/login`) → logout → login, with no console errors and all requests visibly proxied through `/api/v1/...` rather than hitting the backend origin directly.

---

## [2026-07-25] — Milestone 3: Public Investor Library, Discovery Feed & Follows

### Added
- Migration `0003`: `strategy_categories`, `portfolio_strategy_tags`, `public_investors`, `follows` tables — all speced in [database.md](./database.md) since Phase 0, built now — plus the FK constraint + index on `portfolios.public_investor_id` deferred since migration `0001`.
- Public Investor Library seeded with 5 profiles (Radhakishan Damani, Ashish Kacholia, Vijay Kedia, Dolly Khanna, Mukul Agrawal), each with real, dated, cited holdings pulled from live shareholding-disclosure sources (`scripts/seed_public_investors.py`) — no fabricated or estimated figures, per [database.md](./database.md)'s explicit requirement.
- Discovery Feed v1: `GET /discovery/investors` (filter by strategy, sort by recency/portfolio-age/alphabetical — no "most followed," per [product-requirements.md](./product-requirements.md)), `GET /discovery/strategy-categories`, cached in Redis with sync-triggered invalidation.
- `GET /public-investors`, `GET /public-investors/:slug`.
- Follows: `POST/DELETE /portfolios/:id/follow`, `GET /users/me/following` — no capital, no execution.
- Investor Strategy Overview: rules-based, descriptive-only summary copy folded into `GET /portfolios/:id/analytics`, reusing Milestone 2's analytics output.
- Portfolio Activity (ADR-015): `GET /portfolios/:id/activity` — descriptive diffs between consecutive syncs, computed on read, no new table.
- 30 new tests (116 total).

### Fixed
- `discovery_service.list_investors` combined `SELECT DISTINCT` with an `ORDER BY` expression not in the select list — SQLite tolerates this, Postgres doesn't (`InvalidColumnReference`). Caught by testing against the real local Postgres container, not by the (SQLite-backed) pytest suite. Fixed by computing the total count before adding sort/eager-load, and removing `DISTINCT` entirely once it was clear none of the joins here can produce duplicate rows.
- `strategy_overview_service`'s concentration/market-cap boundary conditions: an exactly-even 4-sector split (HHI == 0.25) was worded as "weighted toward" one sector instead of "diversified"; an exact 50/50 market-cap split was worded as "predominantly" one category. Both fixed to require strictly-greater-than at the boundary.

### Notes
- An initial attempt to seed `Holding.avg_cost_price` for Public Investor Library entries (back-derived from each holding's disclosed value) produced a share price roughly 60x off from the real one on a spot check — see the design note in [decisions.md](./decisions.md) alongside ADR-015. Left blank instead; these portfolios currently show no computed analytics, honestly.
- `GET /portfolios/:id/history` (raw snapshot history) has been documented in [api.md](./api.md) since Phase 0 but still isn't built — tracked in [feature-backlog.md](./product/feature-backlog.md), out of scope for this milestone.
- Scope was backend-only, same shape as Milestone 2. Frontend, a second broker, and Account Aggregator remain out of scope — see [decisions.md](./decisions.md).

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
