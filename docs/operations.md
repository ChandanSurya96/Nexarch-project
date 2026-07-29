# Operations

**Purpose:** How Nexarch is deployed, monitored, backed up, recovered, and rotated — the runbooks an on-call person follows at 3am, written before they're needed rather than during the incident. See [security.md](./security.md) for the security posture these procedures protect, and [architecture.md](./architecture.md) for the system they operate.

**Status honesty:** Nexarch has **no production deployment yet**. Everything below is written and, where possible, *tested* — the backup/restore drill has been executed for real; the deploy workflow has never run, because the Railway project doesn't exist. Steps that are unexercised are marked as such rather than presented as proven.

---

## Topology

| Component | Platform | Notes |
|---|---|---|
| Frontend (Next.js) | Vercel | Deploys from its own Git integration, not from our workflow |
| API (Flask/gunicorn) | Railway | `apps/api/Dockerfile`, `CMD` = gunicorn |
| Sync worker (Celery) | Railway | Same image, `celery -A app.celery_app worker` |
| Beat scheduler (Celery) | Railway | Same image, `celery -A app.celery_app beat` |
| PostgreSQL | Railway managed | Automated backups by the platform, plus ours |
| Redis | Railway managed | Cache + queue + rate limits + refresh-token families |

API and worker deliberately share one image (ADR-040) — separate images would let the two drift, and a worker running different code than the API is a miserable class of bug.

## Required environment variables

Set in Railway (API + worker + beat all need these). Values come from your secret store — **never** commit them, and never paste them into a chat, ticket, or log.

| Variable | Required | Notes |
|---|---|---|
| `DATABASE_URL` | **yes** | Railway provides it |
| `REDIS_URL` | **yes** | Railway provides it; must not be localhost in production |
| `JWT_SECRET` | **yes** | ≥32 chars. `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `ENCRYPTION_KMS_KEY_ID` | **yes** | ≥32 chars. **See the rotation warning below — this one is special.** |
| `FLASK_ENV` | **yes** | `production` |
| `UPSTOX_API_KEY` / `_SECRET` / `_REDIRECT_URI` | yes | From the Upstox developer console |
| `SENTRY_DSN` | optional | Unset = error tracking silently off (ADR-041) |
| `APP_RELEASE` | optional | Set by the deploy workflow to the git SHA |

The app **refuses to start** in production if any of the first four are missing, empty, or a placeholder (ADR-039). That's deliberate: before this validation existed, a deploy with `JWT_SECRET` unset started cleanly and issued JWTs signed with the empty string — forgeable for any user id, with `/health` and `/health/ready` both reporting green. Verified against the real app, not theorised. A refused boot is the correct, loud failure.

## Deploying

CI (`.github/workflows/ci.yml`) runs on every PR and push to `main`: backend lint/format/migrate/test against real Postgres and Redis, frontend lint/typecheck/test/build. **A red CI means do not deploy.**

Deploy is `.github/workflows/deploy.yml`, **manually triggered** (Actions → Deploy → type `deploy`). Manual on purpose: there's no staging environment yet to catch a bad build, so a human decides each production change. See "Promoting to automatic deploys" below.

Order matters and is enforced by the workflow:

1. **Migrations first**, to completion, before the new image takes traffic. Deploying first and migrating after means new code runs against the old schema for the length of the migration.
2. **Then** the API/worker deploy.

After deploying, verify:

```bash
curl -fsS https://<api-host>/health        # liveness: process is up
curl -fsS https://<api-host>/health/ready  # readiness: DB + Redis reachable
```

`/health/ready` returning 503 with `NOT_READY` means a dependency is unreachable — check the `checks` object in the body for which one.

## Rolling back

**Rolling back code does not roll back a migration.** This is the single most important thing on this page.

1. **Code-only change** → redeploy the previous image in Railway. Done.
2. **Change that included a migration** → decide first: *is the new schema backward-compatible with the old code?*
   - **Yes** (added a nullable column, added an index): roll the code back and leave the schema. Safe, and the usual case.
   - **No** (dropped/renamed a column, tightened a constraint): rolling code back alone will break. Either roll forward with a fix, or run `flask db downgrade <previous_revision>` **and** verify the downgrade actually works — some don't. Migration `0006`, for example, deliberately raises `NotImplementedError` on downgrade because reversing a Postgres enum addition requires rebuilding the type by hand.

Check what's deployed before deciding:

```bash
flask db current   # schema revision the database is on
flask db heads     # revision the code expects
```

## Backups and restore

Railway's managed Postgres takes its own automated backups. `scripts/backup_db.sh` exists for what those don't give you: a portable artifact you control, a pre-migration safety copy, and something you can practise restoring.

**Redis is deliberately not backed up.** It holds only cache and queue state — the discovery cache, the historical-price cache (ADR-037), rate-limit counters, and refresh-token families. Losing it costs latency and logs everyone out; it loses no durable data. Do not add Redis backups; add the understanding that Redis is disposable.

```bash
# Back up (writes a timestamped custom-format dump + SHA-256)
DATABASE_URL='postgresql://...' ./scripts/backup_db.sh ./backups

# Restore into a scratch database — NEVER practise against production
./scripts/restore_db.sh ./backups/nexarch-<ts>.dump 'postgresql://.../scratch_db'
```

`restore_db.sh` refuses a target whose URL contains `prod`/`production` unless `ALLOW_PRODUCTION_RESTORE=yes` is set, because the point of a drill is to restore somewhere safe.

### The restore drill (do this quarterly, and before beta)

A backup nobody has restored is a hypothesis. The drill:

1. Take a backup.
2. Restore it into a scratch database.
3. Confirm the checksum verified (`<file>: OK`).
4. Compare the printed row counts against the source.
5. Confirm `SELECT version_num FROM alembic_version` matches.
6. Drop the scratch database.

**Last executed:** 2026-07-29, against the dev database — checksum OK, row counts matched exactly (users 9, portfolios 6, holdings 23, snapshots 2, broker_connections 1, follows 3, audit_logs 51), schema `0007` on both sides. That drill also caught a real portability bug: Alpine's BusyBox `sha256sum` rejects `--check` (GNU-only), so verification failed inside the postgres container. Fixed to use `-c`, which both accept. Worth noting the script failed *safe* — it refused to restore an unverified dump rather than continuing.

## Secret rotation

General procedure: generate the new value → set it in Railway → redeploy → verify → revoke the old value at its source. Per-secret specifics below, because they are **not** interchangeable.

### `JWT_SECRET` — safe to rotate, logs everyone out

Rotating invalidates every access and refresh token immediately. All users must log in again. No data is lost. Refresh-token families (ADR-030) are keyed in Redis and become unreachable — harmless, they expire on their own.

Do it during low traffic, and expect a support spike, not an incident.

### `ENCRYPTION_KMS_KEY_ID` — **cannot currently be rotated without breaking every broker connection**

This is a known limitation, documented rather than discovered during an incident (ADR-043).

`encryption_service` wraps a per-record data key with this master secret, but stored ciphertext carries **no key-version marker**, and the code has no way to try an old key. Change this value and **every stored broker access token becomes permanently undecryptable** — every user's broker connection breaks and each must reconnect. There is no recovery path, because there's nothing recorded that says which key encrypted which row.

Right now the blast radius is zero: there are no production users. That is exactly why this needs fixing *before* beta, not after.

To make rotation possible, `encryption_service` needs key-versioning: prefix stored ciphertext with a key id, keep the previous key available during a transition, decrypt with whichever key the row names, and re-encrypt rows to the new key in a background pass. That's tracked as a pre-beta task, not done here.

**Until then:** if this secret is ever exposed, the honest response is to rotate it *and* accept that all users must reconnect their brokers — and to say so plainly to them.

### Broker API keys (`UPSTOX_API_KEY` / `_SECRET`)

Rotate in the Upstox developer console, update Railway, redeploy. Existing user access tokens are unaffected (they're issued under the app's credentials, not equal to them), but a rotation may invalidate in-flight OAuth flows — users mid-connection retry.

### Database credentials

Railway rotates and updates `DATABASE_URL` together; redeploy to pick it up. Take a backup first.

## Monitoring and alerting

Built (ADR-034, ADR-041):

- **Structured JSON logs** with a per-request correlation id, echoed to the client as `X-Request-ID`. Given a user's request id, you can find every log line for that request.
- **`audit_logs`** — the durable record of `connect`/`disconnect`/`sync`/`login`/`logout`/`token_refresh`/`refresh_reuse_detected`/`error`.
- **Health endpoints** — `/health` (liveness) and `/health/ready` (readiness).
- **Sentry**, inert until `SENTRY_DSN` is set. PII is off (`send_default_pii=False`) and a scrubber redacts secret-shaped keys, because request bodies here carry passwords and broker OAuth codes.

**Alerts to configure once Sentry is connected** (recommended, not auto-created):

| Signal | Why it matters |
|---|---|
| Any `refresh_reuse_detected` audit event | Strong token-theft signal (ADR-030), not routine expiry |
| Spike in sync `error` audit events | Broker outage, expired credentials, or a sync regression |
| 5xx rate above baseline | Anything from a bad deploy to a dependency failure |
| `/health/ready` failing | DB or Redis unreachable — user-visible within seconds |
| Celery queue depth growing | Workers dead or wedged; syncs silently stop |

## Incident response

`security.md` requires this before real broker tokens are stored in production.

1. **Assess.** User-facing? Data exposed? Check `/health/ready`, Sentry, Railway logs, and `audit_logs`.
2. **Contain.** For a suspected credential compromise, rotate the affected secret *first* (see above — and read the `ENCRYPTION_KMS_KEY_ID` warning before touching that one). For a bad deploy, roll back.
3. **Communicate.** For anything touching user data, tell affected users plainly what happened and what you did. India's DPDP Act carries breach-notification obligations — see [security.md](./security.md).
4. **Record.** Timeline, impact, root cause, fix, prevention.
5. **Follow up.** Turn the prevention item into a real task, not a good intention.

**On-call:** solo founder. There is no rotation, and no escalation path. That is a real limitation to state rather than paper over — it means response time is bounded by one person's availability, which is a launch consideration for beta scope and the SLA you promise (or deliberately don't).

## Promoting to automatic deploys

Deploy is manual today because there's no staging environment. Before switching to deploy-on-merge, all of these should be true:

1. A staging environment mirroring production, deployed automatically from `main`.
2. Smoke tests running against staging post-deploy.
3. The `ENCRYPTION_KMS_KEY_ID` rotation gap closed.
4. At least one rehearsed rollback.
5. Alerting live and verified — someone actually receives an alert.
