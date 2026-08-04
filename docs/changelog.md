# Changelog

**Purpose:** Chronological record of major features, architectural changes, and releases. Format follows [Keep a Changelog](https://keepachangelog.com) conventions. See [decisions.md](./decisions.md) for the *reasoning* behind entries here — this file is the *what and when*, that one is the *why*.

---

## [Unreleased]

Nothing pending beyond what's logged below — this section stays as the running head for whatever's currently in progress.

---

## [2026-08-04] — Documentation architecture audit

No code changed. The documentation set was restructured so that volatile state lives in one place, and every reality-dependent claim was re-verified against the implementation. Five statements turned out to be false and are corrected below — three of them had been wrong for months.

### Added
- **[CURRENT_STATE.md](./CURRENT_STATE.md)** — the canonical snapshot of the repository *today*: stage, per-area status, open PRs, blockers, priorities, a maturity breakdown, and the current test/lint/CI results with the date each was measured. Volatile state now has one owner instead of being spread across `README.md`, `roadmap.md` and `CLAUDE.md`. Ends with the recommended reading order for a fresh session, ordered volatile → stable.
- **[TECHNICAL_DEBT.md](./TECHNICAL_DEBT.md)** — 15 verified debt items across backend, frontend, infrastructure, documentation and product, each with description, why it exists, impact, suggested fix and priority. Every item cites a file, a line, or a measurement; nothing was recorded on suspicion. Closes with the four items that need a founder decision rather than engineering.
- **[OPERATIONAL_GOTCHAS.md](./OPERATIONAL_GOTCHAS.md)** — the traps that have actually cost time here: the `apps/web` submodule workflow, the Black config-root trap, the absent Prettier, `next dev` versus `next build`, the two backend test preconditions, Postgres ENUM migrations, and the `git show rev:path` failure in Git Bash.
- **`Last verified: YYYY-MM-DD`** blocks on the six documents whose accuracy depends on the code rather than on philosophy. `broker-integrations.md` gets a split block, because its implementation status and its broker-terms research age at completely different rates.

### Fixed — documentation that disagreed with the implementation
- **`docs/README.md` claimed Phase 2 shipped "the Dhan integration".** It did not. `integrations/broker/` contains only `base.py`, `registry.py` and `upstox.py`, and the registry registers `upstox` alone. The work exists as commit `81f5e20` on the local branch `feature/milestone-8-dhan-broker`, **unmerged and unpushed to origin** — so it lives on one machine. `changelog.md` had recorded this accurately at the time; the status summary had not. Nexarch supports exactly **one** broker in any deployable state.
- **`api.md` documented two endpoints that don't exist** — `PATCH /api/v1/users/me` and `GET /api/v1/users/:username`. Verified by enumerating every route decorator in `app/routes/`. `users_bp` registers exactly three routes: `/me`, `/me/following`, `/me/portfolio`. Both are now listed as not implemented, with a note on what would need deciding to add them.
- **`architecture.md` listed a `strategy_categories` blueprint** that has never existed. `strategy-categories` is a route on the discovery blueprint. The real list is seven blueprints, and `health` was missing from it.
- **`architecture.md` said portfolio-health metrics are cached in Redis.** They aren't — `analytics_service.py` touches Redis nowhere. They're computed on sync and **persisted in Postgres** on the snapshot row, which is what makes the history and comparison endpoints possible. A TTL cache would be the wrong storage for them.
- **`security.md` said no error-tracking service was wired and that an incident-response runbook "should exist".** Both were superseded by the Deployment slice: Sentry is wired (inert without a DSN, ADR-041), and `operations.md` has carried an incident-response runbook since ADR-039–043.
- **`development-guide.md` claimed "ESLint + Prettier, run in CI and as a pre-commit hook".** Prettier is not a dependency, has no config, and there are no pre-commit hooks anywhere. This claim is why `npx prettier` was reached for once and reformatted 26 files at 80 columns.
- **`roadmap.md` marked Phase 0 as *(current)***, four phases after it stopped being current, and listed two Phase 2 items — additional brokers, and Watchlists — that were never delivered. Both are now marked, with the Watchlists question ("is this meaningfully different from follows?") stated rather than dropped.

### Changed
- **`CLAUDE.md` refactored into a stable operating manual** — philosophy, non-negotiables, working process, repository structure, architecture rules, conventions, operational rules, commands, and a definition of done. All volatile state moved to `CURRENT_STATE.md`; it now opens by pointing there.
- **`docs/README.md` reduced to navigation.** The status block moved to `CURRENT_STATE.md` and the changelog-style entries were removed as duplicates of `changelog.md`. It gains an explicit **documentation-boundaries table** naming what each document does and does not own.
- **`architecture.md`'s system diagram now says it shows the intended shape, not the built one** — six brokers and the Account Aggregator path are what the adapter abstraction exists to support, not what runs. The sync flow gained the windowed fan-out (ADR-046) and `/health/sync` (ADR-047), neither of which had reached this document.
- `security.md` gained the login-timing guarantee (122x → 1.08x, measured), which had been recorded in ADRs and the changelog but never in the security posture itself.

### Notes
- **Measured during the audit, not carried forward:** 326 backend tests pass (3m37s), 42 frontend tests pass across 12 files, `ruff` and `black --check` both clean across 67 files. Backend figures require `docker compose up -d`.
- **CI has not produced a passing run since 2026-07-31.** Every run since — including PR #13's — sat queued until cancelled, under both `ubuntu-latest` and the Blacksmith runner labels. No job ever started, so nothing failed on code. The cause is most likely account-level and can only be confirmed from the GitHub account. Recorded in `CURRENT_STATE.md` as the top blocker.
- Two claims were verified by breaking them deliberately and restoring: removing `apps/api/.env` aborts pytest during **collection** (not "~38 individual failures", as had been believed), and stopping Docker turns 61 tests into `NoneType` errors that read as application bugs.

---

## [2026-08-04] — Frontend: Design System & Marketing Landing Page

Presentation work, running alongside the operational pre-beta list rather than reopening engineering hardening. **No backend, API, routing, auth or business-logic change.** Lives in the `apps/web` submodule (`ChandanSurya96/nexarch-web`) across two commits; this repo carries the pointer bump. See ADR-048 through ADR-050.

### Added
- **Composition primitives** (ADR-048) — `components/ui` now owns the page shell (`PageContainer`, `ContentWidth`, `PageHeader`, `PageSection`, `SectionTitle`, `SectionDivider`), the card look (`Surface`, `DataCard`, `InfoRow`/`InfoList`), every figure (`Metric`, `Eyebrow`, `StatCard`), the auth shell (`AuthLayout`, `Field`) and loading states (`Skeleton` presets). Every route was migrated onto them; `Card`, `Figure`, `Section`, the standalone `StatCard` and `PortfolioFingerprint` were deleted as duplicates. The type scale is expressed as roles rather than per-screen pixel values.
- **Portfolio Identity Strip** — a portfolio's sector mix drawn to scale as one band, in three variants, sharing `lib/sectorColors.ts` with the donut chart and the holdings-table dots so the three views reinforce one legend. It renders **nothing** when allocation data is absent: no placeholder, no equal-weight fallback. The `tiny` variant is consequently unused, because the discovery and library endpoints don't return `sector_allocation` — the four backend fields blocking specific UI are now listed in [design-system.md](./design-system.md).
- **Marketing landing page** at `/` (ADR-049), recreated from a Figma source: nine sections in `components/landing/`, each its own file. The fingerprint visual is **computed, not drawn** — concentric contour rings generated from sector weights via a sine envelope — so it is exact at any size and costs no image request. `SiteNav` returns `null` on `/`, which now supplies its own navigation.
- **`lib/format.ts`** — one place for `Intl` formatting. Percentages pin `minimumFractionDigits` equal to `maximumFractionDigits`, so figures stay aligned down a column instead of ragged.
- **Framer Motion** (ADR-050), confined to the landing route and loaded through `LazyMotion` + `m` so only `domAnimation` ships. Route JS **49.2 kB → 38.2 kB** against a direct `motion` import; shared JS unchanged at 106 kB. This supersedes the "motion is CSS, not Framer Motion" note recorded a few days earlier, and restores what `design-system.md` originally specified.

### Fixed
- **Seven WCAG AA contrast failures in the Figma spec itself**, which had never had a contrast pass run against it. The worst two: `#fff` on the `#6C8EFF` accent fill — the **primary call to action** — measures **2.60:1**, and the spec's `#3E4250` tertiary text measures **1.97:1** on the page background. Each is corrected against a measured ratio, commented in place with both numbers.
- **`--text-tertiary` in the product palette was below AA.** Estimated at 4.6:1, it measured **4.09:1**; now `#828291`. Caught by sweeping the live DOM, not by arithmetic — which was wrong twice, the second time by validating a corrected token against only two of the four surfaces it appears on. Contrast is now measured with full ancestor alpha compositing; a first sweep that ignored alpha reported `ratio: 1` false positives by comparing elements against themselves.
- **`/profile` rendered no `<main>`** while `RequireAuth` showed its fallback, which made the global skip link a dead link on every guarded route (WCAG 2.4.1).
- **Comparison table columns were asymmetric** (154px vs 147px) because `table-layout: auto` sizes by content — a side-by-side comparison that isn't visually even undermines the neutrality the feature exists to convey. Now `table-fixed`.
- A `focus-visible:outline-none` with no replacement style, introduced during the migration, removed from `InvestorCard`.

### Changed
- Two pieces of Figma content overridden deliberately, both for the same reason the product refuses to invent a sector allocation: sample verification records attributed to **real named public figures** (including a sitting regulator) against invented filing references were replaced with unmistakably fictional ones, and a "BROKER VERIFIED" line naming a broker Nexarch does not integrate now names one it does.

### Notes
- **Known copy issue, flagged not fixed:** the landing page's broker-flow section names four brokers, two of which aren't built. Settle before the page is public.
- **Verification was against the Figma source's numeric values** — every size, weight, tracking and colour confirmed in the live DOM — not a side-by-side pixel diff. Strong evidence for type and spacing; it would not catch a compositional misreading.
- Verified across 375 / 768 / 1024 / 1440, with lint, typecheck, 42 tests and a production build green.
- Two self-inflicted formatting incidents, both now written into [development-guide.md](./development-guide.md): `npx prettier` reformatted 26 files at 80 columns despite not being a dependency and having no config, and `black` given a path outside `apps/api` reformatted 68 files at line-length 88 — the same config-root trap recorded in the previous entry, hit a second time.

---

## [2026-07-31] — Phase 2.5, Slice 5: Review Fixes & Operational Hardening — **Beta Candidate**

Closes the engineering review's findings. No new product surface; this is the last hardening slice before the first real deployment.

### Security fixes
- **Account enumeration via login response timing.** `authenticate_user` spelled its check as `user is None or not bcrypt.check_password_hash(...)`, and `or` short-circuits — so an unknown email never reached bcrypt and was rejected in **2.8 ms**, while a registered address paid the full cost factor: **338.8 ms**. Identical response bodies don't help when the clock answers the question. Login now always performs exactly one bcrypt verification, against a per-process random dummy hash when the email is unknown. Measured after: **365.5 ms vs 337.9 ms, ratio 1.08x** (was 122x). `scripts/benchmark_login_timing.py` reproduces both. The dummy hash derives from the app's own configured cost factor, so raising `BCRYPT_LOG_ROUNDS` can't silently reopen the gap.
- **Encryption master key is now rotatable** (ADR-044), superseding ADR-043's "fix before beta". Stored tokens carry a key-version prefix, several keys can be configured at once, and `scripts/rewrap_encryption_keys.py` re-wraps existing rows. **No schema change and no data migration** — an unversioned value is unambiguously version 1. Verified by executing a rotation, not arguing it: a token written in the genuine pre-ADR-044 format was rotated to v2, the v1 key was then removed entirely, and the plaintext returned byte-identical. The dev database's real token — written months ago by the old code — also decrypts unchanged.

### Fixed
- **`reconnect` was never in `audit_event_type_enum`** — latent since Milestone 2. Every broker *reconnect* (the routine path; Kite-style tokens expire daily) hit `InvalidTextRepresentation` and returned **500 in production**, after the connection row had already committed. Invisible for three hardening slices because the suite ran on SQLite, which doesn't enforce enums; CI's first run against real Postgres caught it immediately. Migration `0008`, plus `tests/test_audit_log_enum.py`, which parses every `log_event` call site and fails on SQLite in under a second — the same bug had already shipped once (0006).
- **Duplicate audit rows per login.** Route *and* service both wrote a `login` event, doubling the success side of any failed-vs-successful ratio computed from `audit_logs` during an incident. The service owns it; the route call is gone.
- **Discovery returned 500 whenever Redis was unreachable.** `list_investors` called Redis with no error handling — the same failure mode as the `/health` outage bug in ADR-034. Now degrades to uncached.
- **CI never checked out `apps/web`** (a submodule), so the frontend job had been failing on its first real run.

### Added
- **Sync-pipeline monitoring** (ADR-047) — `GET /health/sync`, with four independent checks: scheduler alive, worker alive, a recent successful sync, and the share of connections stuck in `error`. Built on Redis heartbeats and Postgres only; no external provider. The pipeline's worst failure is silence — if Beat dies, nothing raises and every other endpoint stays green while holdings quietly go stale. Deliberately *not* part of `/health/ready`: a dead scheduler must never pull healthy API instances out of the load balancer. Checks whose signal is unavailable report `null`, not unhealthy.
- **Scheduled sync is spread across a window** (ADR-046) — shuffled, batched (`SYNC_BATCH_SIZE`, 20) across `SYNC_WINDOW_MINUTES` (120) with jitter, instead of firing every connection at 02:00:00. Broker rate limits are per-application, so the old fan-out spiked with total users and got worse precisely as the product succeeded.
- **O(1) discovery cache invalidation** (ADR-045) — one `INCR` on a namespace counter, replacing `SCAN` + a `DELETE` per key on every sync completion. `SCAN` walks the whole keyspace, so the cost was set by unrelated data sharing the Redis instance.

### Notes
- **Deployment rehearsal is deliberately not done, and is marked blocked** — a real rehearsal needs the Railway and Vercel projects, which don't exist yet. Migrations, Docker startup, graceful shutdown and the backup/restore drill were all exercised locally in Slice 4; an actual deploy cannot be rehearsed against infrastructure that isn't provisioned, and writing a runbook step nobody has run is the failure mode this phase exists to eliminate.
- Three bugs this slice were found by *running* things rather than reading them: the rotation script called a database with a missing key perfectly healthy (`key_version_of` parses a prefix and needs no key); the cache version counter's "never set" fallback of 1 collided with `INCR`'s first return value of 1, making the first invalidation a silent no-op; and the new sync heartbeats leaked into real dev Redis from a test that had no Redis fake — the same leak the price cache had in Slice 3.
- One self-inflicted mistake worth recording: running `black` with a path outside `apps/api` moved its config root to the repo root, which has no `pyproject.toml`, so it silently reformatted **68 files** at line-length 88 instead of the configured 100. Re-running at 100 does *not* undo it — black's magic trailing comma makes the round trip lossy — so the fix was `git checkout` of every unintended file.

---

## [2026-07-29] — Phase 2.5, Slice 4: Deployment & Operations

### Security fix
- **Production refused to fail.** `create_app("production")` with `JWT_SECRET` unset started cleanly and issued JWTs signed with the empty string — forgeable for **any user id**, a complete authentication bypass, with `/health` and `/health/ready` both reporting green. Verified empirically against the real app. `config.py`'s docstring had claimed the opposite ("defaults are intentionally non-functional so a missing .env fails loudly"). New `app/config_validation.py` (ADR-039) now refuses to boot production when `JWT_SECRET`/`ENCRYPTION_KMS_KEY_ID` are missing, empty, placeholders, or under 32 chars, or when `DATABASE_URL`/`REDIS_URL` are unset or localhost. Dev and testing are unaffected.

### Added
- **CI** (`.github/workflows/ci.yml`, ADR-040) — backend lint/format/migrate/test against real Postgres and Redis service containers; frontend lint/typecheck/test/build. `development-guide.md` has claimed "PRs require passing CI" since Phase 0 with nothing enforcing it.
- **Deploy** (`.github/workflows/deploy.yml`) — manual, typed-confirmation, migrations run to completion *before* traffic cutover. Never yet executed; the Railway project doesn't exist.
- **Containerisation** — `apps/api/Dockerfile` + `.dockerignore`, one image for API and worker, gunicorn, non-root, healthcheck.
- **Sentry** (ADR-041) — completely inert unless `SENTRY_DSN` is set. `send_default_pii=False` plus a scrubber, because request bodies here carry passwords and broker OAuth codes.
- **Backup/restore** (`scripts/backup_db.sh`, `scripts/restore_db.sh`, ADR-042) — checksummed dumps, restore with row-count verification, and a guard refusing production-looking targets.
- **`docs/operations.md`** — deploy, rollback, restore drill, secret rotation, monitoring, and the incident-response runbook `security.md` required pre-launch.

### Notes
- **`ENCRYPTION_KMS_KEY_ID` cannot currently be rotated** (ADR-043). `encryption_service` records no key version, so changing it makes every stored broker token permanently undecryptable and forces all users to reconnect. Blast radius is zero today (no production users) — which is why it's named now rather than found during an incident. Key-versioning is a pre-beta task, tracked in `roadmap.md`, deliberately not done here.
- The **restore drill was executed for real**, and immediately earned its keep: Alpine's BusyBox `sha256sum` rejects `--check` (GNU-only), so verification failed inside the postgres container. Fixed to `-c`. The script failed *safe*, refusing to restore an unverified dump.
- The **Dockerfile originally broke graceful shutdown** — shell-form `CMD` left `/bin/sh` as PID 1, so SIGTERM never reached gunicorn and in-flight requests would be killed rather than drained on every deploy. Fixed with `exec`; verified by observing `[1] Shutting down: Master` on `docker stop`.
- Pre-existing lint/format debt (one unused import, three unformatted files) was cleaned up so CI is green on its first run rather than red on arrival.
- Container verified end-to-end: refuses to boot unconfigured, serves both health endpoints when configured, shuts down gracefully.

---

## [2026-07-27] — Phase 2.5, Slice 3: Performance & Database Hardening

No user-facing feature changes and no intended change in externally visible behavior — this slice makes the existing platform faster and bounded under growth.

### Changed
- **Discovery feed no longer loads snapshot history** (ADR-036). It was eager-loading `Portfolio.snapshots` so a Python `max()` could pick each portfolio's latest health — **7,300 ORM objects materialized for a 20-item page** at one year of daily syncs, growing forever. Replaced with one batched `ROW_NUMBER()` query. Measured **589.6 ms → 82.5 ms** (~7×), and the cost no longer scales with history depth.
- **Opt-in eager loading** on `get_visible_portfolio` for the paths that actually serialize a portfolio: `/portfolios/:id` −1 query, `/profile` −1, `/compare` −2.
- **Historical price fetching** de-duplicates instruments, caches series in Redis (24 h TTL — past daily closes are immutable), and sends only cache misses through a bounded thread pool (default 4) (ADR-037). Previously one sequential broker call per holding, with the same ISIN refetched independently for every portfolio holding it.
- **Indexes** (migration `0007`, ADR-035): added `portfolio_strategy_tags(strategy_category_id)`; replaced the snapshot index with `(portfolio_id, snapshot_date DESC, created_at DESC)` to match the actual ORDER BY; **dropped `ix_holdings_sector`**, verified unused by any query and rebuilt on every sync for zero reads.
- **Discovery cache** now caches only the first 5 pages — the key embeds caller-controlled `page`, so unbounded paging could mint unlimited Redis keys (ADR-038).

### Added
- Opt-in pagination on `GET /portfolios/:id/history` and `/activity` (ADR-038). Omit the params and the response is byte-identical to before; supply `page`/`per_page` for a bounded slice plus `meta.pagination`.
- `scripts/benchmark_endpoints.py` — seeds a disposable `nexarch_bench` database (60 portfolios × 365 snapshots) and reports query counts plus wall-vs-database time per endpoint, so before/after is reproducible.
- `tests/test_query_performance.py` — query-shape regression guards, both verified to fail against the pre-change code.
- `HISTORICAL_PRICE_CONCURRENCY` and `HISTORICAL_PRICE_CACHE_TTL_SECONDS` config.

### Fixed
- **Discovery and analytics could report different health for the same portfolio.** `resolve_latest_health` ranked snapshots by `snapshot_date` alone while `get_latest_snapshot` ordered by `(snapshot_date, created_at)` — so for two snapshots sharing a calendar date, which one won was nondeterministic and endpoint-dependent. Exactly the inconsistency ADR-025 exists to prevent. Now both use the same ordering; a regression test reproduces the old behaviour as `0.11 != 0.99`.

### Notes
- Measurement discipline mattered more than intuition here. The headline bug had a completely healthy query count (6) — only the gap between wall time and database time exposed it, and only at seeded volume; the dev database's 2 snapshots hid it entirely.
- Two self-inflicted mistakes worth recording: applying eager loading unconditionally first made `/history` (2→5 queries) and `/compare` (16→20) *worse* before opt-in fixed it; and an initial `DISTINCT ON` implementation would have silently returned the **oldest** snapshot per portfolio on SQLite, since SQLAlchemy ignores `DISTINCT ON` there — caught by a deprecation warning, not by a failing test.
- Honest scope limit: opt-in pagination bounds the *response*, not the underlying query — the full history is still read and sliced in Python. Genuinely bounding the read needs cursor-based pagination, logged as remaining debt.

---

## [2026-07-27] — Phase 2.5, Slice 2: Reliability & Observability

### Added
- Sync-pipeline retry policy (ADR-034): `sync_portfolio_task` retries a rate-limited broker call up to 3 times with exponential backoff (capped at 10 minutes) — safe because nothing is written to the database before that failure can occur. Token-expiry and unexpected errors are never retried.
- Every `run_sync` failure path — token-expiry, rate-limit (on final attempt), generic API error, and the previously-uncaught tail (normalization/DB-write/health-metric/categorization errors) — now consistently sets `connection.status`, writes a structured log line, and writes an `audit_logs` "error" event. Before this, the last category was completely silent: no status update, no log, no audit row.
- `sync_all_active_connections` (the daily scheduled sync) now retries connections marked `"error"` (transient rate-limit/API failures), not just `"active"` ones — previously a connection that hit a rate limit once would silently drop out of every future scheduled sync, forever.
- `task_acks_late`/`task_reject_on_worker_lost` added to the Celery config — a worker crash or OOM mid-sync no longer silently loses the task; it's redelivered to another worker instead.
- Structured (JSON) application logging (`app/logging_config.py`) — every log line carries a timestamp, level, message, and a per-request correlation id (`X-Request-ID` response header, echoed into every log line for that request). Previously there was exactly one logging call in the entire backend.
- `GET /health` (liveness) and `GET /health/ready` (readiness — checks DB and Redis, both now with explicit short timeouts) — no health-check endpoints existed before this.
- New backend test files: `test_sync_tasks.py`, `test_health.py`, `test_logging_config.py`, plus new failure-branch tests in `test_sync_service.py`.

### Notes
- Scoped from `docs/roadmap.md`'s Phase 2.5 "Reliability" bullet, which no prior ADR had turned into a concrete design. A Plan-agent review that read the actual Celery 5.4/Kombu source caught a critical bug in the first draft before it shipped: the rate-limit exception handler was swallowing the error and returning normally, which would have made the new retry config a silent no-op.
- "Monitoring and alerting" was deliberately scoped to foundation-only this slice (structured logs, health endpoints, audit-log consistency) — no external alerting/APM service (Sentry, Datadog, etc.) is wired in, since there's nowhere to alert into yet and picking one is a real commitment better tied to the Deployment slice's hosting decision.
- A genuinely dangerous testing gotcha was found and fixed while writing this slice's own tests: `sync_all_active_connections` is itself a Celery task, and calling it directly (rather than via `.run()`) silently pushes a *different* Flask app context — one built from ambient environment config, not the pytest session's test config — pointing queries at real dev Postgres/Redis with no error to signal it. See ADR-034 and `test_sync_tasks.py`'s own docstring.
- Performance and Deployment are the next two hardening slices, in that order, before beta launch — see `docs/roadmap.md` "Phase 2.5."

---

## [2026-07-26] — Phase 2.5, Slice 1: Security & API Hardening

### Added
- `app/error_handlers.py` (ADR-029) — every failure path (missing/expired/malformed token, unmatched route, unhandled exception) returns the documented `{ data, meta, error }` envelope instead of flask-jwt-extended's or Werkzeug's own default response.
- `app/services/refresh_token_service.py` (ADR-030) — refresh-token rotation with family-based reuse detection. A `fid` claim shared by both tokens at login, tracked in Redis; reusing a stale jti outside a 10-second grace window (tolerating a benign concurrent-tab race) kills the whole session family, forcing re-login. `POST /auth/logout` now has a real server-side effect it didn't have before.
- CSRF protection actually enabled (`JWT_COOKIE_CSRF_PROTECT = True`, ADR-031) — previously documented in `docs/security.md` as if it were. In practice only gates `POST /auth/refresh`, the one cookie-authenticated endpoint.
- Rate limiting via `flask-limiter`, Redis-backed (ADR-032) — previously documented in `docs/api.md` as if it were. Login: 5/minute, 20/hour. Register: 10/hour. Everything else: 100/minute default.
- Unique constraint on `broker_connections.user_id` (ADR-033, migration `0005`) — a real database-level backstop for the one-connection-per-user rule, converting a previously-acknowledged app-level TOCTOU race into a clean `409 BROKER_ALREADY_CONNECTED`.
- `GET /users/me/following` is now paginated (`app/schemas/pagination.py`'s shared `PaginationQuerySchema`, reused by `DiscoveryQuerySchema` too) — the one list endpoint left unbounded. Frontend's `useFollowingIds` requests `per_page=100`.
- `/portfolios/compare`'s hand-rolled `ids` query-string parsing replaced with a proper marshmallow schema (`CompareQuerySchema`), matching the validation convention every other endpoint uses.
- Frontend: `lib/api.ts` attaches the CSRF header automatically; `AuthProvider.logout()` refreshes and retries once if the access token has already expired from idling, so an idle-then-logout user's session is still revoked server-side.
- 6 new backend test modules/additions (`test_error_handlers.py`, `test_rate_limiting.py`, reuse-detection/CSRF/logout tests in `test_auth.py`, pagination tests in `test_follows.py`, an `IntegrityError`-path test in `test_broker_connections.py`), 3 new frontend test files/additions (`api.test.ts`, `useFollowingIds.test.tsx`, logout-retry tests in `AuthProvider.test.tsx`).

### Notes
- Scoped from a production-readiness audit (security/database/API/performance/operational/deployment/documentation review) that found several places where the docs described protections or behavior the code didn't actually have — this slice closes those specific gaps rather than a general refactor. `docs/security.md`'s CORS section was also rewritten: no CORS config exists (or is needed) on the Flask side, since the frontend proxies same-origin (ADR-016) — the doc previously described CORS config as the mitigation, which was never actually built. The secret-rotation-runbook claim in the same doc was similarly softened to reflect that none exists yet — deferred to the Deployment hardening slice, once a real secrets manager is chosen.
- Milestone 8 (Dhan broker integration) was built and verified in the same working session but is a separate, still-uncommitted slice of work — not part of this entry, and not merged into this branch's history. Its ADR-029/030 equivalents (Dhan limitations, cross-broker guard) would be renumbered on top of whichever of these two slices merges first.
- Reliability, Performance, and Deployment are the next three hardening slices, in that order, before beta launch — see `docs/roadmap.md` "Phase 2.5."

---

## [2026-07-26] — Milestone 7: Rules-Based Strategy Categorization (Phase 2)

### Added
- Rules-based auto-categorization for verified portfolios (ADR-028): `strategy_categorization_service.py` evaluates 3 of the platform's 8 fixed strategy categories against currently-synced data — Small-cap Specialist (market-cap allocation `> 50%`), Low-risk (volatility `<= 15%`), Momentum (trailing ~90-day return `>= 10%`) — and recomputes `PortfolioStrategyTag` rows on every sync (deleted and reinserted, never accumulated), the same idempotent pattern already used for `Holding` rows. `ensure_strategy_category_rows()` creates the 8 canonical rows at runtime if they don't exist yet, rather than relying on a migration or the Public Investor Library seed script having run.
- `analytics_service.compute_momentum_return`/`compute_portfolio_momentum` — trailing value-weighted return, reusing the exact same per-holding historical-closes fetch already pulled for volatility (no new broker API calls). Persisted in `health_metrics` as `momentum`, alongside `volatility`.
- `GET /portfolios/:id/analytics` gains `strategy_categorization`: a list of `{slug, name, explanation}` for each matched category, computed fresh at read time from the current snapshot — each explanation cites the actual observed number against its threshold, never a bare label or a synthesized confidence score (ADR-007). Always `[]` for Public Investor Library portfolios (manually curated, not rule-derived) and for portfolios with no snapshot yet.
- Frontend: `PortfolioProfileView` gives each strategy-tag `Badge` a tooltip with its explanation (when one exists), and a conditional Momentum `StatCard` next to the existing Volatility one.
- New "Feature: Strategy Categorization" section in `docs/product-requirements.md`.
- 34 new backend tests (`TestMomentum`/`TestComputePortfolioMomentum` in `test_analytics_service.py`; new `test_strategy_categorization_service.py`; `TestStrategyTagging` in `test_sync_service.py`; new tests in `test_portfolios.py`/`test_discovery.py`), 4 new frontend tests.

### Notes
- Real limitation, stated plainly (ADR-028): Growth, Value, Dividend, ETF, and Long-term are **not** auto-assigned this milestone — no fundamentals/valuation/dividend data or instrument-type classification exists anywhere in this codebase, and Long-term has no validated stability threshold without real production sync history to calibrate against. All 8 categories remain in the taxonomy and filterable; only 3 can appear on a verified portfolio automatically.
- This milestone is what makes a verified (broker-synced) portfolio able to match a Discovery Feed strategy filter for the first time — previously only the 5 seeded Public Investor Library entries ever had tags.
- Manually verified: seeded/synced a verified portfolio designed to cross each of the 3 thresholds, confirmed tags + explanations on `GET .../analytics`, confirmed it appeared under `GET /discovery/investors?strategy=<slug>`, confirmed a second sync with different data replaced tags rather than accumulating them, and confirmed Public Investor Library entries were completely unaffected.

---

## [2026-07-26] — Milestone 6: Portfolio Comparison (Phase 2)

### Added
- `GET /api/v1/portfolios/compare?ids=<uuid>,<uuid>` (ADR-026) — side-by-side analytics for two portfolios plus a computed diff (`total_value`, `sector_allocation`, `health`). Computed entirely on read from existing data; no new table or migration.
- `analytics_service.compute_scalar_diff`/`compute_allocation_diff`/`compute_health_diff` — pure, nullable-safe diff functions. `compute_allocation_diff` distinguishes a sector genuinely at 0% (a real snapshot that just doesn't hold it) from a whole side having no snapshot at all (`None` — "unknown," not a fabricated zero).
- `portfolio_comparison_service.py` (new) — coordinator reusing `portfolio_profile_service.get_detail`/`get_analytics_view` for each portfolio, same visibility rules as every other portfolio endpoint. Rejects comparing a portfolio to itself (`400 CANNOT_COMPARE_SAME_PORTFOLIO`).
- Frontend: `lib/types/comparison.ts`, `usePortfolioComparison` hook, `PortfolioComparisonView` + `ComparisonStatRow` components, `/compare` page. Entry points: "Compare with mine" on `InvestorCard` (Discover + Library) and on the portfolio detail page, shown only when the viewer has their own portfolio and isn't viewing it (ADR-027 — link-only entry, no dedicated picker this milestone).
- New `Feature: Portfolio Comparison` section in `docs/product-requirements.md` (didn't exist before this milestone).
- 12 new backend tests (`TestScalarDiff`/`TestAllocationDiff`/`TestHealthDiff` in `test_analytics_service.py`; `TestCompare` in `test_portfolios.py`), 3 new frontend tests.

### Notes
- Manually verified end-to-end: seeded two verified portfolios with distinct sector allocations/health metrics, confirmed the `/compare` page's health table, both allocation charts, and the sector-diff callout render correctly; confirmed a verified-vs-unsynced-Public-Investor-Library comparison shows every field as honestly unknown (`—` / "Not enough data to compare"), not zeros — this caught and fixed a real bug where an unsynced side's missing sectors were defaulting to a fabricated `0.0` in the diff instead of `null`.

---

## [2026-07-25] — Fix: nondeterministic latest-snapshot ordering (ADR-025)

### Added
- `portfolio_snapshots.created_at` (migration `0004`) — a server-generated UTC timestamp, backfilled for existing rows in the same statement that adds the column.

### Fixed
- `get_latest_snapshot`, `get_snapshot_history` (`portfolio_service.py`), and `get_activity` (`activity_service.py`) all ordered by `snapshot_date` alone, which isn't unique per portfolio — more than one sync can land on the same calendar date (a scheduled sync plus a manual "sync now," or two manual syncs past the cooldown). Without a secondary sort key, which same-date row `/analytics` returned as "current" was genuinely undefined. All three now sort by `(snapshot_date, created_at)`. Found while explaining, on request, whether a stored volatility figure is immutable — it surfaced that "latest" itself wasn't well-defined in the same-day case.
- `test_portfolios.py::TestGetAnalytics::test_with_snapshot_returns_health_metrics` asserted `"volatility" not in health` against a hand-built `health_metrics` dict that simply never included the key — accurate by coincidence, not by the actual current contract (`volatility` has been a real, nullable field since Milestone 5). Updated to assert `is None`.

### Notes
- `snapshot_date`/uniqueness was deliberately left alone — multiple same-day snapshots are legitimate, independent events, not a bug; see ADR-025 for why a `UNIQUE` constraint + upsert was rejected.
- The existing `(portfolio_id, snapshot_date)` index wasn't extended to include `created_at` — same-date row counts per portfolio are small enough (bounded by the sync cooldown) that the extra in-memory sort is negligible.

---

## [2026-07-25] — Milestone 5: Health Metrics (Phase 2, first slice)

### Added
- Portfolio volatility (ADR-024, resolving ADR-008): annualized, value-weighted standard deviation of daily log returns, computed from Upstox's own Historical Candle Data API using the same broker access token already stored per connection — no new market-data vendor. `BrokerAdapter.fetch_historical_prices` (+ `PricePoint`), implemented in `UpstoxAdapter`; `analytics_service.compute_volatility`/`compute_portfolio_volatility`; wired into `sync_service.run_sync` via `_fetch_closes_by_holding_id`, with per-holding fetch failures isolated so one bad ISIN doesn't fail the whole sync.
- `health.volatility` (nullable) added to the analytics response and to `PortfolioProfileView`'s health `StatCard` grid — rendered only when non-null, never a placeholder.
- `GET /portfolios/:id/history` — documented in `docs/api.md` since Phase 0, built now: raw `total_value`/`diversification_score`/`volatility` per snapshot, oldest to newest. `portfolio_service.get_snapshot_history`, `PortfolioHistoryEntrySchema`, `usePortfolioHistory` hook, and a new `HistoryChart` (Recharts line chart with the same accessible-table pattern as `AllocationChart`) rendered on the profile view once 2+ snapshots exist.
- `test_sync_service.py` — `run_sync` had no dedicated test file before this milestone (only exercised via `smoke_test.py` and indirectly through mocked `.delay()` calls); added alongside the new volatility-wiring logic.
- 13 new backend tests, 4 new frontend tests.

### Fixed
- Two existing tests encoded ADR-008's original "no volatility field at all" constraint (`test_no_volatility_field` in `test_analytics_service.py`, an equivalent check in `smoke_test.py`) — updated to the new convention this milestone establishes: `volatility` is a real field, honestly `null` when it can't be computed, not absent.

### Notes
- Real limitation, stated plainly: volatility only covers verified (Upstox-connected) portfolios. Public Investor Library portfolios have no broker token to fetch historical prices with, so they remain without it — the same pre-existing gap as every other health metric for that portfolio type (ADR-015's design note), not a new one.
- Manually verified via a targeted script exercising `compute_volatility`/`compute_portfolio_volatility` against hand-built price series, and the full `/history` + `/analytics` response shapes against seeded snapshot data.

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
