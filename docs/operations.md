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
| `ENCRYPTION_KMS_KEY_ID` | **yes** | ≥32 chars. Key version 1. See "Rotating `ENCRYPTION_KMS_KEY_ID`" below. |
| `ENCRYPTION_KEYS` | no | Multi-key form for rotations only: `1:<secret>,2:<secret>` (ADR-044). |
| `ENCRYPTION_ACTIVE_KEY_VERSION` | no | Which key new tokens use. Defaults to the highest configured. |
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

### `ENCRYPTION_KMS_KEY_ID` — rotate with zero user reconnects (ADR-044)

> This section previously said this key **could not** be rotated without breaking every broker connection (ADR-043). That gap is now closed. Stored tokens name the key version that wrapped them, several keys can be configured at once, and `scripts/rewrap_encryption_keys.py` moves rows onto a new key without ever decrypting the token itself.

**Never skip step 4.** Retiring a key while rows still reference it is the one irreversible mistake here — those data keys become unrecoverable and the affected users must reconnect their brokers.

**1. Check the starting state.**

```bash
apps/api/venv/bin/python scripts/rewrap_encryption_keys.py --status
```

Every version listed must read `active` or `readable, awaiting re-wrap`. If anything says `UNREADABLE`, stop and fix the configuration first — the command also exits non-zero. It verifies by actually unwrapping a data key, not by checking whether a version appears in config, so "the key is set" and "the key is correct" are not confused.

**2. Add the new key alongside the old one, and make it active.**

```
ENCRYPTION_KEYS=1:<old secret>,2:<new secret>
ENCRYPTION_ACTIVE_KEY_VERSION=2
```

Set both in Railway and redeploy. From this moment new tokens are wrapped with version 2 while existing ones still decrypt with version 1 — no user is affected, and this state is safe to sit in indefinitely.

**3. Re-wrap the existing rows.**

```bash
apps/api/venv/bin/python scripts/rewrap_encryption_keys.py --dry-run
apps/api/venv/bin/python scripts/rewrap_encryption_keys.py --apply
```

Safe to re-run; a crash partway leaves a mix of key versions, which the application reads normally. Only each row's small data key is re-wrapped — the token ciphertext is copied byte-for-byte, so no plaintext broker token is ever held in memory.

**4. Confirm, then retire the old key.**

```bash
apps/api/venv/bin/python scripts/rewrap_encryption_keys.py --status
```

Only when it reports `0 token(s) not yet on the active key` and no `UNREADABLE` rows, drop version 1:

```
ENCRYPTION_KEYS=2:<new secret>
ENCRYPTION_ACTIVE_KEY_VERSION=2
```

**Rollback.** Before step 4, rollback is free: set `ENCRYPTION_ACTIVE_KEY_VERSION=1` and re-run `--apply` to move rows back. Both keys stay configured, so nothing is unreadable at any point. After step 4 there is no rollback — which is why step 4 is gated on step 1's check.

**If this secret is exposed**, rotate it with the procedure above. Users are unaffected and need not be asked to reconnect; treat it as a credential-rotation incident, not a user-facing breakage.

**On restore:** a database restored into an environment configured with different keys still can't be read — see `restore_db.sh`'s warning. Restore the key configuration alongside the data.

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
2. **Contain.** For a suspected credential compromise, rotate the affected secret *first* (see above; `ENCRYPTION_KMS_KEY_ID` has its own multi-step procedure). For a bad deploy, roll back.
3. **Communicate.** For anything touching user data, tell affected users plainly what happened and what you did. India's DPDP Act carries breach-notification obligations — see [security.md](./security.md).
4. **Record.** Timeline, impact, root cause, fix, prevention.
5. **Follow up.** Turn the prevention item into a real task, not a good intention.

**On-call:** solo founder. There is no rotation, and no escalation path. That is a real limitation to state rather than paper over — it means response time is bounded by one person's availability, which is a launch consideration for beta scope and the SLA you promise (or deliberately don't).

## Promoting to automatic deploys

Deploy is manual today because there's no staging environment. Before switching to deploy-on-merge, all of these should be true:

1. A staging environment mirroring production, deployed automatically from `main`.
2. Smoke tests running against staging post-deploy.
3. ~~The `ENCRYPTION_KMS_KEY_ID` rotation gap closed.~~ Done — ADR-044.
4. At least one rehearsed rollback.
5. Alerting live and verified — someone actually receives an alert.
