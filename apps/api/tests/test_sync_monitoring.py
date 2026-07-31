"""Sync-pipeline monitoring and fan-out scheduling (ADR-046, ADR-047).

The pipeline's worst failure is silence: if Beat dies or every worker stops,
nothing raises and every existing endpoint stays green while holdings go
quietly stale. These tests cover the signals that make that condition
observable, and the fan-out change that stops the daily sync being a
self-inflicted thundering herd.
"""

from datetime import UTC, datetime, timedelta

import pytest

from app.models.broker_connection import BrokerConnection
from app.models.user import User
from app.services import sync_monitor_service
from app.tasks.sync import _schedule_offsets

SYNC_HEALTH_URL = "/health/sync"

THRESHOLDS = {
    "scheduler_max_age_hours": 26,
    "worker_max_age_hours": 26,
    "success_max_age_hours": 50,
    "max_error_ratio": 0.5,
}


@pytest.fixture(autouse=True)
def fake_redis(monkeypatch):
    """In-memory stand-in, per the project's no-live-dependency testing rule."""
    store: dict[str, str] = {}

    def _set(key, value, ex=None):
        store[key] = value

    monkeypatch.setattr("app.services.sync_monitor_service.redis_client.get", store.get)
    monkeypatch.setattr("app.services.sync_monitor_service.redis_client.set", _set)
    return store


def _make_connection(db, *, status="active", last_synced_at=None, suffix="a"):
    user = User(
        email=f"sync-monitor-{suffix}@example.test",
        username=f"syncmon{suffix}",
        password_hash="x",
    )
    db.session.add(user)
    db.session.flush()

    connection = BrokerConnection(
        user_id=user.id,
        broker_name="upstox",
        connection_method="broker_api",
        access_token_encrypted="v1.fake.fake",
        status=status,
        last_synced_at=last_synced_at,
    )
    db.session.add(connection)
    db.session.commit()
    return connection


class TestFanoutScheduling:
    """ADR-046 — the daily sync must not start every connection at once."""

    def test_offsets_are_spread_across_the_window(self):
        offsets = _schedule_offsets(count=100, window_seconds=7200, batch_size=20)
        assert len(offsets) == 100
        assert min(offsets) >= 0
        assert max(offsets) <= 7200
        # Spread, not clustered: the last connection must start substantially
        # later than the first, which is the entire point.
        assert max(offsets) > 3600

    def test_batch_size_bounds_concurrent_starts(self):
        """At most batch_size syncs may begin within one batch interval."""
        count, window, batch = 100, 7200, 20
        offsets = _schedule_offsets(count, window, batch)
        batch_interval = window / (count // batch)

        for start in range(0, window, int(batch_interval)):
            in_window = [o for o in offsets if start <= o < start + batch_interval]
            assert len(in_window) <= batch * 2, (
                "more than two batches' worth of syncs start inside one batch "
                f"interval ({len(in_window)}) — the fan-out is not bounded"
            )

    def test_offsets_within_a_batch_are_jittered(self):
        """Batching alone would fire each batch at one identical instant."""
        offsets = _schedule_offsets(count=20, window_seconds=7200, batch_size=20)
        assert len(set(offsets)) > 1, "all syncs in a batch share one start time"

    def test_empty_and_single_connection_are_handled(self):
        assert _schedule_offsets(0, 7200, 20) == []
        single = _schedule_offsets(1, 7200, 20)
        assert len(single) == 1 and 0 <= single[0] <= 7200

    def test_fewer_connections_than_batch_size_still_spread(self):
        """The common early case — must not regress to a single instant."""
        offsets = _schedule_offsets(count=5, window_seconds=7200, batch_size=20)
        assert len(set(offsets)) == 5


class TestSchedulerHeartbeat:
    def test_missing_heartbeat_is_unknown_not_unhealthy(self, db):
        """A fresh deployment must not page anyone."""
        status = sync_monitor_service.get_sync_status(**THRESHOLDS)
        assert status["checks"]["scheduler"]["healthy"] is None
        assert status["healthy"] is True

    def test_recent_heartbeat_is_healthy(self, db):
        sync_monitor_service.record_scheduler_heartbeat()
        status = sync_monitor_service.get_sync_status(**THRESHOLDS)
        assert status["checks"]["scheduler"]["healthy"] is True

    def test_stale_heartbeat_is_unhealthy(self, db, fake_redis):
        stale = datetime.now(UTC) - timedelta(hours=30)
        fake_redis["sync:heartbeat:scheduler"] = stale.isoformat()

        status = sync_monitor_service.get_sync_status(**THRESHOLDS)
        assert status["checks"]["scheduler"]["healthy"] is False
        assert status["healthy"] is False
        assert status["checks"]["scheduler"]["age_seconds"] > 26 * 3600


class TestWorkerHeartbeat:
    def test_stale_worker_is_unhealthy(self, db, fake_redis):
        """Beat alive but no worker consuming — queueing into the void."""
        sync_monitor_service.record_scheduler_heartbeat()
        fake_redis["sync:heartbeat:worker"] = (datetime.now(UTC) - timedelta(hours=30)).isoformat()

        status = sync_monitor_service.get_sync_status(**THRESHOLDS)
        assert status["checks"]["scheduler"]["healthy"] is True
        assert status["checks"]["worker"]["healthy"] is False

    def test_worker_heartbeat_recorded_by_task_helper(self, db, fake_redis):
        sync_monitor_service.record_worker_heartbeat()
        assert "sync:heartbeat:worker" in fake_redis


class TestRecentSuccess:
    def test_no_connections_is_healthy(self, db):
        """Nothing to sync is the correct pre-launch state, not a failure."""
        status = sync_monitor_service.get_sync_status(**THRESHOLDS)
        assert status["checks"]["recent_success"]["healthy"] is None
        assert status["healthy"] is True

    def test_recent_success_is_healthy(self, db):
        _make_connection(db, last_synced_at=datetime.now(UTC) - timedelta(hours=2), suffix="ok")
        status = sync_monitor_service.get_sync_status(**THRESHOLDS)
        assert status["checks"]["recent_success"]["healthy"] is True

    def test_stale_success_is_unhealthy(self, db):
        """Everything can look alive while every sync fails at the broker."""
        _make_connection(db, last_synced_at=datetime.now(UTC) - timedelta(hours=72), suffix="stale")
        status = sync_monitor_service.get_sync_status(**THRESHOLDS)
        assert status["checks"]["recent_success"]["healthy"] is False
        assert status["healthy"] is False

    def test_connections_that_never_synced_are_unknown(self, db):
        _make_connection(db, last_synced_at=None, suffix="never")
        status = sync_monitor_service.get_sync_status(**THRESHOLDS)
        assert status["checks"]["recent_success"]["healthy"] is None


class TestFailureRate:
    def test_all_healthy_connections_pass(self, db):
        _make_connection(db, status="active", last_synced_at=datetime.now(UTC), suffix="f1")
        status = sync_monitor_service.get_sync_status(**THRESHOLDS)
        assert status["checks"]["failure_rate"]["healthy"] is True

    def test_majority_in_error_is_unhealthy(self, db):
        now = datetime.now(UTC)
        _make_connection(db, status="error", last_synced_at=now, suffix="e1")
        _make_connection(db, status="error", last_synced_at=now, suffix="e2")
        _make_connection(db, status="active", last_synced_at=now, suffix="e3")

        status = sync_monitor_service.get_sync_status(**THRESHOLDS)
        check = status["checks"]["failure_rate"]
        assert check["healthy"] is False
        assert check["connections_in_error"] == 2
        assert status["healthy"] is False

    def test_a_single_failure_among_many_does_not_alert(self, db):
        """One user revoking access is normal and must not page anyone."""
        now = datetime.now(UTC)
        _make_connection(db, status="error", last_synced_at=now, suffix="s1")
        for i in range(4):
            _make_connection(db, status="active", last_synced_at=now, suffix=f"s{i + 2}")

        status = sync_monitor_service.get_sync_status(**THRESHOLDS)
        assert status["checks"]["failure_rate"]["healthy"] is True


class TestSyncHealthEndpoint:
    def test_healthy_returns_200(self, client, db):
        resp = client.get(SYNC_HEALTH_URL)
        assert resp.status_code == 200
        assert resp.get_json()["data"]["status"] == "ok"

    def test_unhealthy_returns_503_with_measurements(self, client, db, fake_redis):
        fake_redis["sync:heartbeat:scheduler"] = (
            datetime.now(UTC) - timedelta(hours=40)
        ).isoformat()

        resp = client.get(SYNC_HEALTH_URL)
        assert resp.status_code == 503
        body = resp.get_json()
        assert body["error"]["code"] == "SYNC_UNHEALTHY"
        assert "scheduler" in body["error"]["message"]
        # A 503 with no numbers makes whoever is paged go and find them.
        assert body["meta"]["checks"]["scheduler"]["age_seconds"] > 26 * 3600

    def test_response_uses_the_documented_envelope(self, client, db):
        body = client.get(SYNC_HEALTH_URL).get_json()
        assert set(body) == {"data", "meta", "error"}

    def test_is_exempt_from_rate_limiting(self, client, db):
        """Same reasoning as /health (ADR-034) — a monitoring endpoint that
        429s under its own uptime check is useless."""
        for _ in range(15):
            assert client.get(SYNC_HEALTH_URL).status_code in (200, 503)


class TestMonitoringNeverBreaksTheThingItMonitors:
    def test_redis_failure_does_not_raise(self, db, monkeypatch):
        def _boom(*_args, **_kwargs):
            raise ConnectionError("redis is down")

        monkeypatch.setattr("app.services.sync_monitor_service.redis_client.get", _boom)
        monkeypatch.setattr("app.services.sync_monitor_service.redis_client.set", _boom)

        sync_monitor_service.record_scheduler_heartbeat()  # must not raise
        status = sync_monitor_service.get_sync_status(**THRESHOLDS)
        assert status["checks"]["scheduler"]["healthy"] is None

    def test_corrupt_heartbeat_value_is_treated_as_missing(self, db, fake_redis):
        fake_redis["sync:heartbeat:scheduler"] = "not-a-timestamp"
        status = sync_monitor_service.get_sync_status(**THRESHOLDS)
        assert status["checks"]["scheduler"]["healthy"] is None
