"""Health-check endpoints (ADR-034).

Unprefixed (not under /api/v1) — every other blueprint takes its prefix at
registration time in create_app(), not baked into the blueprint, so this is
purely additive. No auth, no rate limit: deployment platforms (and Docker's
own healthcheck convention already used for postgres/redis in
docker-compose.yml) expect an unauthenticated, fast-responding probe.

limiter.exempt(health_bp) below is load-bearing, not decorative: flask-
limiter's own hit-tracking runs in before_request, ahead of any route code,
and RATELIMIT_STORAGE_URI is Redis-backed outside tests — so without this
exemption, a Redis outage makes the *rate limiter itself* raise before
liveness/readiness ever get a chance to run, turning /health into exactly
as dependent on Redis as /health/ready, defeating the entire point of a
liveness probe that's supposed to stay up when a dependency doesn't.
Caught live: manually stopping Redis and hitting /health during this
slice's own verification returned 500, not the unaffected 200 it should.
"""

from __future__ import annotations

from flask import Blueprint
from sqlalchemy import text

from app.extensions import db, limiter, redis_client
from app.utils.responses import error, success

health_bp = Blueprint("health", __name__)
limiter.exempt(health_bp)


@health_bp.get("/health")
def liveness():
    """Confirms the process is up. Checks no dependencies on purpose —
    a liveness probe should never fail because Postgres or Redis is down;
    that's what /health/ready is for."""
    return success({"status": "ok"})


@health_bp.get("/health/ready")
def readiness():
    """Confirms the app can actually serve traffic — DB and Redis are
    both reachable. Each check has an explicit short timeout (see
    app/extensions.py's RedisClient.init_app) so a hung dependency fails
    this probe quickly instead of hanging it."""
    checks = {"database": False, "redis": False}

    try:
        db.session.execute(text("SELECT 1"))
        checks["database"] = True
    except Exception:
        pass

    try:
        redis_client.ping()
        checks["redis"] = True
    except Exception:
        pass

    if all(checks.values()):
        return success({"status": "ok", "checks": checks})
    unreachable = [name for name, ok in checks.items() if not ok]
    return error("NOT_READY", f"Unreachable: {', '.join(unreachable)}.", 503)
