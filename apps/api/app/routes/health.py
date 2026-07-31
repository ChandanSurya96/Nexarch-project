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

from flask import Blueprint, current_app, jsonify
from sqlalchemy import text

from app.extensions import db, limiter, redis_client
from app.services import sync_monitor_service
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


@health_bp.get("/health/sync")
def sync_health():
    """Whether the background sync pipeline is actually running (ADR-047).

    Deliberately separate from /health/ready. Readiness answers "should this
    instance receive traffic", and a dead Celery Beat must never pull the API
    out of the load balancer — the API is fine, the pipeline isn't. This is a
    monitored endpoint, not an orchestration probe: point an uptime check at
    it and alert on 503.

    503 means at least one condition is definitely breached. Conditions whose
    signal is simply unavailable (a fresh deployment that has never synced)
    report `null` and do not fail the probe — alerting on a system's first
    hour is how an alert gets ignored.
    """
    status = sync_monitor_service.get_sync_status(
        scheduler_max_age_hours=current_app.config["SYNC_SCHEDULER_MAX_AGE_HOURS"],
        worker_max_age_hours=current_app.config["SYNC_WORKER_MAX_AGE_HOURS"],
        success_max_age_hours=current_app.config["SYNC_SUCCESS_MAX_AGE_HOURS"],
        max_error_ratio=current_app.config["SYNC_MAX_ERROR_RATIO"],
    )

    if status["healthy"]:
        return success({"status": "ok", "checks": status["checks"]})

    failing = [name for name, check in status["checks"].items() if check.get("healthy") is False]
    # Built inline rather than via error(): the standard envelope's error
    # branch carries no payload, and a monitoring endpoint that returns 503
    # with no measurements makes whoever is paged go and find them by hand.
    # The checks go under `meta`, which is where the documented envelope
    # (ADR-029, docs/api.md) puts non-error detail — the envelope's shape is
    # unchanged, so error() itself doesn't need widening for one caller.
    # Failing names are also in the message, so an alert that only forwards
    # the message is still actionable.
    body = {
        "data": None,
        "meta": {"checks": status["checks"]},
        "error": {
            "code": "SYNC_UNHEALTHY",
            "message": (
                f"Sync pipeline unhealthy: {', '.join(failing) or 'dependency unavailable'}."
            ),
            "status": 503,
        },
    }
    return jsonify(body), 503
