"""Celery tasks — broker sync jobs (Milestone 2).

sync_portfolio_task is enqueued directly on a successful broker-connection
callback (queued within seconds, per docs/product-requirements.md) and via
the manual "sync now" endpoint. sync_all_active_connections runs on the daily
Celery Beat schedule configured in app/celery_app.py.
"""

from __future__ import annotations

from app.celery_app import celery_app
from app.models.broker_connection import BrokerConnection


@celery_app.task(name="sync_portfolio_task")
def sync_portfolio_task(broker_connection_id: str) -> None:
    from app.services.sync_service import run_sync

    run_sync(broker_connection_id)


@celery_app.task(name="sync_all_active_connections")
def sync_all_active_connections() -> None:
    """Daily scheduled sync for every active broker connection.

    Long-term holdings don't need intraday freshness (see
    docs/broker-integrations.md "Refresh Strategy").
    """
    connection_ids = [
        str(row.id) for row in BrokerConnection.query.filter_by(status="active").all()
    ]
    for connection_id in connection_ids:
        sync_portfolio_task.delay(connection_id)
