"""Operational monitoring for the scheduled sync pipeline (ADR-047).

The sync pipeline's worst failure mode is silence. If Celery Beat stops, or
every worker dies, nothing raises, nothing 500s, and every endpoint stays
green — holdings simply get quietly staler until a user notices their
portfolio is a week old. Slice 2 made individual sync *failures* loud
(ADR-034); this makes the *absence* of syncs loud, which is a different and
harder problem because there is no event to hook.

Four conditions, deliberately separated because they have different causes
and different fixes:

  scheduler_alive   Beat fired the daily task recently. Beat is a single
                    process with no redundancy — if it dies, nothing else
                    notices.
  worker_alive      A worker actually picked up a sync task. Distinguishes
                    "beat is queueing into the void" from "beat is dead".
  recent_success    At least one sync completed successfully inside the
                    threshold. The end-to-end signal — everything above can
                    look healthy while every sync fails at the broker.
  failure_rate      Connections stuck in "error". Catches the case where
                    syncs run and complete but consistently fail.

No external monitoring provider (that was a deliberate Slice 2 scoping
decision, ADR-034). Heartbeats live in Redis, the outcome signals come from
Postgres — both already required for the app to serve a request at all, so
this adds no new dependency and nothing new to provision.

Consumed by GET /health/sync. Redis heartbeat keys carry a TTL slightly
longer than their alert threshold: an expired key and a stale key mean the
same thing here, so letting Redis forget them keeps the keyspace bounded
without a cleanup job.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from redis.exceptions import RedisError

from app.extensions import redis_client
from app.models.broker_connection import BrokerConnection

logger = logging.getLogger("app")

_SCHEDULER_HEARTBEAT_KEY = "sync:heartbeat:scheduler"
_WORKER_HEARTBEAT_KEY = "sync:heartbeat:worker"
_FANOUT_COUNT_KEY = "sync:last_fanout:count"

# Heartbeat TTLs: comfortably longer than the thresholds that read them, so
# a key expiring is never mistaken for a threshold breach that hasn't
# actually happened yet.
_HEARTBEAT_TTL_SECONDS = 7 * 24 * 60 * 60


def _now() -> datetime:
    return datetime.now(UTC)


def _write_heartbeat(key: str, value: str | None = None) -> None:
    """Record a heartbeat. Never raises — monitoring must not break the thing
    it monitors, and a missing heartbeat already reads as unhealthy, which is
    the correct interpretation of "Redis is down" anyway."""
    try:
        redis_client.set(key, value or _now().isoformat(), ex=_HEARTBEAT_TTL_SECONDS)
    except (RedisError, OSError):
        logger.warning("Failed to write sync heartbeat: key=%s", key, exc_info=True)


def _read_heartbeat(key: str) -> datetime | None:
    try:
        raw = redis_client.get(key)
    except (RedisError, OSError):
        logger.warning("Failed to read sync heartbeat: key=%s", key, exc_info=True)
        return None
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def record_scheduler_heartbeat() -> None:
    """Called by sync_all_active_connections — proves Beat is firing."""
    _write_heartbeat(_SCHEDULER_HEARTBEAT_KEY)


def record_worker_heartbeat() -> None:
    """Called by sync_portfolio_task — proves a worker is consuming."""
    _write_heartbeat(_WORKER_HEARTBEAT_KEY)


def record_fanout(connection_count: int) -> None:
    """How many syncs the last scheduled run queued.

    Zero is meaningful: with connections in the database it means the
    fan-out query is broken, which otherwise looks exactly like a healthy
    quiet night.
    """
    _write_heartbeat(_FANOUT_COUNT_KEY, str(connection_count))


def _age_seconds(timestamp: datetime | None) -> float | None:
    return None if timestamp is None else (_now() - timestamp).total_seconds()


def get_sync_status(
    *,
    scheduler_max_age_hours: int,
    worker_max_age_hours: int,
    success_max_age_hours: int,
    max_error_ratio: float,
) -> dict:
    """Evaluate every sync-health condition. Never raises.

    Returns a dict with an overall `healthy` flag plus one entry per check,
    each carrying the measurement behind its verdict — a probe that says
    "unhealthy" without saying *how* stale is a probe someone has to
    reverse-engineer at 3am.

    A check whose signal is unavailable reports `healthy: None` rather than
    False. On a system that has never run a sync — a fresh deployment — the
    honest answer is "unknown", and paging someone because a brand-new
    environment has no sync history yet is how alerts get muted.
    """
    checks: dict[str, dict] = {}

    scheduler_at = _read_heartbeat(_SCHEDULER_HEARTBEAT_KEY)
    scheduler_age = _age_seconds(scheduler_at)
    checks["scheduler"] = {
        "healthy": (
            None if scheduler_age is None else scheduler_age < scheduler_max_age_hours * 3600
        ),
        "last_run_at": scheduler_at.isoformat() if scheduler_at else None,
        "age_seconds": scheduler_age,
        "threshold_seconds": scheduler_max_age_hours * 3600,
        "detail": (
            "Celery Beat has not fired the daily sync within the threshold"
            if scheduler_age is not None and scheduler_age >= scheduler_max_age_hours * 3600
            else "no scheduled run recorded yet" if scheduler_age is None else "ok"
        ),
    }

    worker_at = _read_heartbeat(_WORKER_HEARTBEAT_KEY)
    worker_age = _age_seconds(worker_at)
    checks["worker"] = {
        "healthy": None if worker_age is None else worker_age < worker_max_age_hours * 3600,
        "last_task_at": worker_at.isoformat() if worker_at else None,
        "age_seconds": worker_age,
        "threshold_seconds": worker_max_age_hours * 3600,
        "detail": (
            "no worker has picked up a sync task within the threshold"
            if worker_age is not None and worker_age >= worker_max_age_hours * 3600
            else "no worker activity recorded yet" if worker_age is None else "ok"
        ),
    }

    # Outcome signals come from Postgres, not Redis: last_synced_at is only
    # written after a sync actually succeeds, so it can't be faked by a
    # worker that started and then died.
    try:
        total = BrokerConnection.query.filter(
            BrokerConnection.status.in_(["active", "error"])
        ).count()
        latest_success = (
            BrokerConnection.query.filter(BrokerConnection.last_synced_at.isnot(None))
            .order_by(BrokerConnection.last_synced_at.desc())
            .first()
        )
        error_count = BrokerConnection.query.filter(BrokerConnection.status == "error").count()
    except Exception:
        logger.warning("Sync monitor could not query connection state", exc_info=True)
        checks["recent_success"] = {"healthy": None, "detail": "database unavailable"}
        checks["failure_rate"] = {"healthy": None, "detail": "database unavailable"}
        return {"healthy": False, "checks": checks}

    last_success_at = latest_success.last_synced_at if latest_success else None
    if last_success_at is not None and last_success_at.tzinfo is None:
        last_success_at = last_success_at.replace(tzinfo=UTC)
    success_age = _age_seconds(last_success_at)

    if total == 0:
        # Nothing to sync is not a failure — pre-launch, and any time every
        # user has disconnected, this is the correct healthy state.
        success_healthy = None
        success_detail = "no syncable connections"
    elif success_age is None:
        success_healthy = None
        success_detail = "connections exist but none has ever synced successfully"
    else:
        success_healthy = success_age < success_max_age_hours * 3600
        success_detail = "ok" if success_healthy else "no successful sync within the threshold"

    checks["recent_success"] = {
        "healthy": success_healthy,
        "last_success_at": last_success_at.isoformat() if last_success_at else None,
        "age_seconds": success_age,
        "threshold_seconds": success_max_age_hours * 3600,
        "syncable_connections": total,
        "detail": success_detail,
    }

    error_ratio = (error_count / total) if total else 0.0
    checks["failure_rate"] = {
        "healthy": None if total == 0 else error_ratio <= max_error_ratio,
        "connections_in_error": error_count,
        "syncable_connections": total,
        "error_ratio": round(error_ratio, 3),
        "threshold_ratio": max_error_ratio,
        "detail": (
            "ok"
            if total == 0 or error_ratio <= max_error_ratio
            else f"{error_count}/{total} connections are in the error state"
        ),
    }

    try:
        last_fanout = redis_client.get(_FANOUT_COUNT_KEY)
    except (RedisError, OSError):
        last_fanout = None
    checks["last_fanout_size"] = {
        "healthy": None,  # informational — never alerts on its own
        "connections_queued": int(last_fanout) if last_fanout and last_fanout.isdigit() else None,
        "detail": "connections queued by the most recent scheduled run",
    }

    # Unknown is not unhealthy. Only a definite False fails the probe.
    healthy = all(check.get("healthy") is not False for check in checks.values())
    return {"healthy": healthy, "checks": checks}
