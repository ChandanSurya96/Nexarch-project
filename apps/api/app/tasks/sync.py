"""Celery tasks — broker sync jobs (Milestone 2).

sync_portfolio_task is enqueued directly on a successful broker-connection
callback (queued within seconds, per docs/product-requirements.md) and via
the manual "sync now" endpoint. sync_all_active_connections runs on the daily
Celery Beat schedule configured in app/celery_app.py.
"""

from __future__ import annotations

from app.celery_app import celery_app
from app.integrations.broker.base import BrokerRateLimitError
from app.models.broker_connection import BrokerConnection


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

    is_final_attempt = self.request.retries >= self.max_retries
    run_sync(broker_connection_id, is_final_attempt=is_final_attempt)


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
    """
    connection_ids = [
        str(row.id)
        for row in BrokerConnection.query.filter(
            BrokerConnection.status.in_(["active", "error"])
        ).all()
    ]
    for connection_id in connection_ids:
        sync_portfolio_task.delay(connection_id)
