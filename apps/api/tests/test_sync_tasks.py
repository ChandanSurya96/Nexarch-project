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

from app.extensions import db
from app.integrations.broker.base import BrokerRateLimitError
from app.models.broker_connection import BrokerConnection
from app.models.user import User
from app.services.encryption_service import encrypt_token
from app.tasks.sync import sync_all_active_connections, sync_portfolio_task


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


class TestSyncAllActiveConnections:
    def test_includes_active_and_error_connections(self, monkeypatch):
        """ADR-034 — "error" is this codebase's status for transient
        rate-limit/API failures; excluding it from the daily beat forever
        was a correctness bug, not intentional design."""
        active = _make_connection("beat-active@example.com", "active")
        errored = _make_connection("beat-error@example.com", "error")
        mock_delay = MagicMock()
        monkeypatch.setattr("app.tasks.sync.sync_portfolio_task.delay", mock_delay)

        sync_all_active_connections.run()

        queued_ids = {call.args[0] for call in mock_delay.call_args_list}
        assert str(active.id) in queued_ids
        assert str(errored.id) in queued_ids

    def test_excludes_expired_connections(self, monkeypatch):
        """Expired means the user needs to reconnect — retrying wastes a
        broker API call and can't fix anything."""
        expired = _make_connection("beat-expired@example.com", "expired")
        mock_delay = MagicMock()
        monkeypatch.setattr("app.tasks.sync.sync_portfolio_task.delay", mock_delay)

        sync_all_active_connections.run()

        queued_ids = {call.args[0] for call in mock_delay.call_args_list}
        assert str(expired.id) not in queued_ids
