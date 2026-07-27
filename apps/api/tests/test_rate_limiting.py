"""Tests for rate limiting (ADR-032).

Rate limiting is genuinely enabled in tests, same as production — see
tests/conftest.py's autouse `_reset_rate_limits` fixture, which resets
flask-limiter's storage before every test. Without that reset, the
route-decorated limits on login/register (which enforce unconditionally
once registered, regardless of Limiter.enabled) would accumulate hits
across the whole session's tests and 429 on ordinary test setup rather
than real abuse.
"""

REGISTER_URL = "/api/v1/auth/register"
LOGIN_URL = "/api/v1/auth/login"


class TestLoginRateLimit:
    def test_sixth_login_attempt_within_a_minute_is_throttled(self, client):
        payload = {"email": "nobody@example.com", "password": "WrongPass1"}
        for _ in range(5):
            resp = client.post(LOGIN_URL, json=payload)
            assert resp.status_code == 401  # unrelated to rate limiting — just wrong creds

        sixth = client.post(LOGIN_URL, json=payload)
        assert sixth.status_code == 429
        body = sixth.get_json()
        assert body["data"] is None
        assert body["error"]["code"] == "TOO_MANY_REQUESTS"

    def test_rate_limit_headers_present(self, client):
        resp = client.post(LOGIN_URL, json={"email": "x@example.com", "password": "WrongPass1"})
        assert "X-RateLimit-Limit" in resp.headers
        assert "X-RateLimit-Remaining" in resp.headers

    def test_a_fresh_test_gets_its_own_quota(self, client):
        """Proves the per-test storage reset actually isolates tests — this
        repeats the first test's exact request volume; if resets weren't
        happening, the shared bucket from the earlier test would already be
        exhausted and the fifth attempt here would 429 instead of the sixth."""
        payload = {"email": "nobody@example.com", "password": "WrongPass1"}
        for _ in range(5):
            resp = client.post(LOGIN_URL, json=payload)
            assert resp.status_code == 401

        sixth = client.post(LOGIN_URL, json=payload)
        assert sixth.status_code == 429


class TestRegisterRateLimit:
    def test_eleventh_register_attempt_within_an_hour_is_throttled(self, client):
        for i in range(10):
            resp = client.post(
                REGISTER_URL,
                json={
                    "email": f"rate-limit-{i}@example.com",
                    "password": "Secure123",
                    "username": f"ratelimit{i}",
                },
            )
            assert resp.status_code == 201

        eleventh = client.post(
            REGISTER_URL,
            json={
                "email": "rate-limit-11@example.com",
                "password": "Secure123",
                "username": "ratelimit11",
            },
        )
        assert eleventh.status_code == 429
        assert eleventh.get_json()["error"]["code"] == "TOO_MANY_REQUESTS"
