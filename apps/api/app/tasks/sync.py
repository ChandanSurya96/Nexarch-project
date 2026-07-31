"""Celery tasks — broker sync jobs (Milestone 2).

sync_portfolio_task is enqueued directly on a successful broker-connection
callback (queued within seconds, per docs/product-requirements.md) and via
the manual "sync now" endpoint. sync_all_active_connections runs on the daily
Celery Beat schedule configured in app/celery_app.py.

The daily sync is **spread across a window**, not fired all at once
(ADR-046). See _schedule_offsets for why.
"""

from __future__ import annotations

import logging
import random

from flask import current_app

from app.celery_app import celery_app
from app.integrations.broker.base import BrokerRateLimitError
from app.models.broker_connection import BrokerConnection
from app.services import sync_monitor_service

logger = logging.getLogger("app")


@celery_app.task(
    name="sync_portfolio_task",
    bind=True,
    # ADR-034 — only BrokerRateLimitError is retried: it's raised before any
    # DB write in run_sync, so a full re-run from scratch on retry is safe by
    # construction. A token-expiry failure needs the user to reconnect (no
    # retry helps), and an unexpected exception fails fast for visibility
    # rather than silently retrying a bug.
    autoretry_for=(BrokerRateLimitError,),
    retry_backoff=True,
    retry_backoff_max=600,
    max_retries=3,
    # Defensive cap so a hung broker call can't block a worker slot forever.
    time_limit=300,
)
def sync_portfolio_task(self, broker_connection_id: str) -> None:
    from app.services.sync_service import run_sync

    # Worker liveness (ADR-047): recorded before the work, so a task that
    # hangs or dies still proves a worker picked it up. "Nothing is being
    # processed" and "processing is failing" are different incidents and
    # need different signals.
    sync_monitor_service.record_worker_heartbeat()

    is_final_attempt = self.request.retries >= self.max_retries
    run_sync(broker_connection_id, is_final_attempt=is_final_attempt)


def _schedule_offsets(count: int, window_seconds: int, batch_size: int) -> list[float]:
    """Countdown (seconds) for each of `count` syncs, spread over the window.

    Every connection used to be enqueued with a bare .delay() the instant
    beat fired, so N users meant N broker calls at 02:00:00 sharp — a
    self-inflicted thundering herd, and the most reliable way to trigger the
    very rate limits ADR-034's retry logic then has to absorb. Brokers rate
    limit per application, so this scales with total users, not per-user
    activity.

    Batching caps how many syncs can start close together; the jitter within
    each batch stops a batch from being its own smaller herd. Both are
    needed: jitter alone still allows an unlucky cluster, and batching alone
    fires each batch at one identical instant.
    """
    if count <= 0:
        return []

    batch_count = max(1, -(-count // batch_size))  # ceil division
    batch_interval = window_seconds / batch_count

    return [
        (index // batch_size) * batch_interval + random.uniform(0, batch_interval)
        for index in range(count)
    ]


@celery_app.task(name="sync_all_active_connections")
def sync_all_active_connections() -> None:
    """Daily scheduled sync for every active *or* recoverable-error connection.

    Long-term holdings don't need intraday freshness (see
    docs/broker-integrations.md "Refresh Strategy"). "error" connections
    (transient rate-limit/API failures) get another daily attempt — a
    rate-limit issue is often gone by the next day, and there is no
    retrying-forever risk here since a genuinely unrecoverable connection
    (an expired token) uses a distinct "expired" status this query still
    excludes, requiring the user to reconnect instead. See ADR-034.

    Enqueued across a configurable window rather than all at once (ADR-046)
    — see _schedule_offsets.
    """
    # Scheduler liveness (ADR-047): proves beat is alive and firing. Written
    # first so a crash later in this function still records that the tick
    # happened — "beat stopped" and "the sync fan-out broke" are different
    # problems and shouldn't look identical.
    sync_monitor_service.record_scheduler_heartbeat()

    connection_ids = [
        str(row.id)
        for row in BrokerConnection.query.filter(
            BrokerConnection.status.in_(["active", "error"])
        ).all()
    ]

    # Shuffled so the spread isn't stable across days. Without this the same
    # accounts would always land in the first batch and the same ones always
    # last — meaning one unlucky user's data is consistently the stalest, and
    # a broker-side incident early in the window always hits the same people.
    random.shuffle(connection_ids)

    window_seconds = current_app.config["SYNC_WINDOW_MINUTES"] * 60
    batch_size = current_app.config["SYNC_BATCH_SIZE"]
    offsets = _schedule_offsets(len(connection_ids), window_seconds, batch_size)

    # strict=True: a length mismatch here would silently drop connections
    # from the day's sync, which is exactly the kind of quiet failure the
    # monitoring in ADR-047 exists to catch. Better to raise.
    for connection_id, countdown in zip(connection_ids, offsets, strict=True):
        sync_portfolio_task.apply_async(args=[connection_id], countdown=countdown)

    logger.info(
        "Scheduled daily sync fan-out: connections=%d window_minutes=%d batch_size=%d "
        "last_start_offset_s=%.0f",
        len(connection_ids),
        current_app.config["SYNC_WINDOW_MINUTES"],
        batch_size,
        max(offsets, default=0),
    )
    sync_monitor_service.record_fanout(len(connection_ids))
