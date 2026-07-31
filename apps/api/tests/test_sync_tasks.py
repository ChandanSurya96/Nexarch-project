"""Tests for app/tasks/sync.py (ADR-034).

No live Celery worker here — same "no live Celery worker" convention
already documented in test_broker_connections.py. Retry config is checked
by inspecting the task object's own attributes rather than actually running
a retry loop.

sync_all_active_connections is itself a @celery_app.task — call it as
`.run()`, never as a bare `()`. Calling it directly invokes Celery's Task
`__call__` (our ContextTask override), which pushes `with
celery_app.py's own flask_app.app_context():` — a SEPARATE Flask app built
by celery_app.py's bare `create_app()` (ambient FLASK_ENV, i.e. whatever
real config .env resolves to), not this test session's "testing" app. That
silently points BrokerConnection.query at real dev Postgres instead of the
test database, with no error to signal it — `.run()` calls the plain
function body directly, using whatever app context is already active (this
test's own), the same way sync_portfolio_task's tests call run_sync
directly rather than the task wrapper.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.extensions import db
from app.integrations.broker.base import BrokerRateLimitError
from app.models.broker_connection import BrokerConnection
from app.models.user import User
from app.services.encryption_service import encrypt_token
from app.tasks.sync import sync_all_active_connections, sync_portfolio_task


@pytest.fixture(autouse=True)
def _fake_sync_monitor_redis(monkeypatch):
    """Keep sync heartbeats out of the real Redis.

    sync_all_active_connections writes scheduler/fan-out heartbeats
    (ADR-047), and this module calls it for real via .run(). Without this
    fake those writes land in the *dev* Redis — which happened, and left
    /health/sync reporting a scheduler heartbeat and a fan-out size of 6
    that no real scheduled run ever produced. Exactly the leak the price
    cache had in Slice 3: real shared Redis outliving a test.
    """
    store: dict[str, str] = {}

    def _set(key, value, ex=None):
        store[key] = value

    monkeypatch.setattr("app.services.sync_monitor_service.redis_client.get", store.get)
    monkeypatch.setattr("app.services.sync_monitor_service.redis_client.set", _set)
    return store


class TestRetryConfig:
    def test_only_rate_limit_errors_are_configured_to_autoretry(self):
        assert sync_portfolio_task.autoretry_for == (BrokerRateLimitError,)

    def test_retry_backoff_is_enabled_with_a_cap_and_bounded_attempts(self):
        assert sync_portfolio_task.retry_backoff is True
        assert sync_portfolio_task.retry_backoff_max == 600
        assert sync_portfolio_task.max_retries == 3

    def test_has_a_defensive_time_limit(self):
        assert sync_portfolio_task.time_limit == 300


def _make_connection(email: str, status: str) -> BrokerConnection:
    user = User(email=email, username=email.split("@")[0], password_hash="x")
    db.session.add(user)
    db.session.flush()

    connection = BrokerConnection(
        user_id=user.id,
        broker_name="upstox",
        connection_method="broker_api",
        access_token_encrypted=encrypt_token("fake-token"),
        status=status,
    )
    db.session.add(connection)
    db.session.commit()
    return connection


def _queued_ids(mock_apply_async) -> set[str]:
    """IDs queued by the fan-out.

    The fan-out uses apply_async(args=[...], countdown=...) rather than
    delay() since ADR-046 — the countdown is what spreads syncs across the
    window instead of firing every connection at 02:00:00 sharp.
    """
    return {call.kwargs["args"][0] for call in mock_apply_async.call_args_list}


class TestSyncAllActiveConnections:
    def test_includes_active_and_error_connections(self, monkeypatch):
        """ADR-034 — "error" is this codebase's status for transient
        rate-limit/API failures; excluding it from the daily beat forever
        was a correctness bug, not intentional design."""
        active = _make_connection("beat-active@example.com", "active")
        errored = _make_connection("beat-error@example.com", "error")
        mock_apply_async = MagicMock()
        monkeypatch.setattr("app.tasks.sync.sync_portfolio_task.apply_async", mock_apply_async)

        sync_all_active_connections.run()

        queued_ids = _queued_ids(mock_apply_async)
        assert str(active.id) in queued_ids
        assert str(errored.id) in queued_ids

    def test_excludes_expired_connections(self, monkeypatch):
        """Expired means the user needs to reconnect — retrying wastes a
        broker API call and can't fix anything."""
        expired = _make_connection("beat-expired@example.com", "expired")
        mock_apply_async = MagicMock()
        monkeypatch.setattr("app.tasks.sync.sync_portfolio_task.apply_async", mock_apply_async)

        sync_all_active_connections.run()

        assert str(expired.id) not in _queued_ids(mock_apply_async)

    def test_every_sync_is_queued_with_a_countdown(self, monkeypatch):
        """ADR-046 — a bare delay() would start every sync simultaneously."""
        for i in range(6):
            _make_connection(f"beat-spread-{i}@example.com", "active")
        mock_apply_async = MagicMock()
        monkeypatch.setattr("app.tasks.sync.sync_portfolio_task.apply_async", mock_apply_async)

        sync_all_active_connections.run()

        countdowns = [call.kwargs["countdown"] for call in mock_apply_async.call_args_list]
        assert countdowns, "nothing was queued"
        assert all(c >= 0 for c in countdowns)
        assert len(set(countdowns)) > 1, "all syncs share one start time — no spread"
