"""A rate-limit store outage must not take the API down with it.

TECHNICAL_DEBT B1. `default_limits` applies to every route and flask-limiter
evaluates limits in `before_request`, ahead of any route code — so an
unreachable Redis raised before the endpoint ran and turned every non-health
route into a 500, including endpoints that touch neither Redis nor the limiter.

Reproduced live on 2026-08-07: the local Redis container stopped mid-session
and `GET /portfolios/compare` returned 500 with a `redis.exceptions.
ConnectionError` raised from `_check_request_limit`, while `/health` stayed
green — the combination that keeps a load balancer sending traffic to instances
that cannot serve any of it.

These tests patch the limiter's storage to raise the way a dead Redis does,
rather than asserting on configuration, so they fail if `swallow_errors` is
removed *or* if a future flask-limiter changes what swallowing covers.
"""

from __future__ import annotations

import pytest
from redis.exceptions import ConnectionError as RedisConnectionError

from app.extensions import limiter


@pytest.fixture
def dead_rate_limit_store(monkeypatch):
    """Make every limiter storage call fail the way an unreachable Redis does."""

    def boom(*args, **kwargs):
        raise RedisConnectionError(
            "Error 10061 connecting to localhost:6379. "
            "No connection could be made because the target machine actively refused it."
        )

    storage = limiter.storage
    monkeypatch.setattr(storage, "incr", boom, raising=False)
    monkeypatch.setattr(storage, "get", boom, raising=False)
    monkeypatch.setattr(storage, "get_expiry", boom, raising=False)
    return storage


class TestApiSurvivesRateLimitStoreOutage:
    def test_unauthenticated_read_still_succeeds(self, client, dead_rate_limit_store):
        resp = client.get("/api/v1/public-investors")
        assert resp.status_code == 200
        assert resp.get_json()["error"] is None

    def test_liveness_probe_unaffected(self, client, dead_rate_limit_store):
        # Already guaranteed by limiter.exempt(health_bp) (ADR-034); asserted
        # here so the two mechanisms are covered by one file.
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_a_rate_limited_auth_route_still_responds(self, client, dead_rate_limit_store):
        """The login route carries its own explicit @limiter.limit.

        Bad credentials, so the assertion is 401 — the point is that the
        request reaches the route at all instead of dying in before_request.
        """
        resp = client.post(
            "/api/v1/auth/login",
            json={"email": "nobody@example.com", "password": "whatever123"},
        )
        assert resp.status_code == 401
        assert resp.get_json()["error"]["code"] == "INVALID_CREDENTIALS"

    def test_response_is_never_a_bare_500(self, client, dead_rate_limit_store):
        """The regression this file exists for."""
        for path in ("/api/v1/public-investors", "/api/v1/discovery/strategy-categories"):
            resp = client.get(path)
            assert resp.status_code != 500, f"{path} 500ed on a rate-limit store outage"
