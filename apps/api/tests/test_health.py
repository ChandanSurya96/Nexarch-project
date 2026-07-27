"""Tests for app/routes/health.py (ADR-034).

Redis is faked here the same way test_discovery.py/test_broker_connections.py
fake it elsewhere — no live Redis server needed, and no dependency on
whether one happens to be running locally.
"""

from __future__ import annotations


def _raise(*args, **kwargs):
    raise ConnectionError("simulated outage")


class TestLiveness:
    def test_always_returns_ok_and_checks_no_dependencies(self, client, monkeypatch):
        # Even with both dependencies broken, liveness must still say ok —
        # it exists specifically so a dependency outage doesn't also kill
        # the liveness probe and get the whole process restarted for no reason.
        monkeypatch.setattr("app.routes.health.redis_client.ping", _raise)
        monkeypatch.setattr("app.routes.health.db.session.execute", _raise)

        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.get_json()["data"]["status"] == "ok"


class TestReadiness:
    def test_ok_when_db_and_redis_reachable(self, client, monkeypatch):
        monkeypatch.setattr("app.routes.health.redis_client.ping", lambda: True)

        resp = client.get("/health/ready")
        assert resp.status_code == 200
        body = resp.get_json()["data"]
        assert body["status"] == "ok"
        assert body["checks"] == {"database": True, "redis": True}

    def test_503_when_redis_unreachable(self, client, monkeypatch):
        monkeypatch.setattr("app.routes.health.redis_client.ping", _raise)

        resp = client.get("/health/ready")
        assert resp.status_code == 503
        assert resp.get_json()["error"]["code"] == "NOT_READY"

    def test_503_when_db_unreachable(self, client, monkeypatch):
        monkeypatch.setattr("app.routes.health.redis_client.ping", lambda: True)
        monkeypatch.setattr("app.routes.health.db.session.execute", _raise)

        resp = client.get("/health/ready")
        assert resp.status_code == 503
        assert resp.get_json()["error"]["code"] == "NOT_READY"


class TestExemptFromRateLimiting:
    def test_health_endpoints_are_never_rate_limited(self, client):
        """Caught live during this slice's own manual verification:
        flask-limiter's hit-tracking runs in before_request, ahead of any
        route code, and its storage is Redis-backed outside tests — so
        without limiter.exempt(health_bp), a Redis outage made the rate
        limiter itself raise before /health ever got a chance to run,
        turning the liveness probe into exactly the kind of
        dependency-coupled endpoint it exists to not be. This can't
        reproduce the original bug directly (tests use memory:// storage,
        which doesn't go down), but it does confirm the actual exemption
        is in effect: well past the default "100 per minute" limit, /health
        must never 429."""
        for _ in range(150):
            resp = client.get("/health")
        assert resp.status_code == 200
