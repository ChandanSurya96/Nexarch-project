"""Tests for app/logging_config.py and the request-id middleware (ADR-034)."""

from __future__ import annotations

import json
import logging


class TestRequestIdCorrelation:
    def test_x_request_id_header_present_and_unique_per_request(self, client):
        resp1 = client.get("/health")
        resp2 = client.get("/health")

        id1 = resp1.headers.get("X-Request-ID")
        id2 = resp2.headers.get("X-Request-ID")
        assert id1 and id2
        assert id1 != id2

    def test_request_id_on_a_log_line_matches_the_response_header(
        self, client, caplog, app, monkeypatch
    ):
        # error_handlers.py's generic Exception handler is the one path
        # guaranteed to log — trigger it the same way test_error_handlers.py
        # does, then confirm the logged record's request_id matches what the
        # client actually received in the response header.
        def _boom(*args, **kwargs):
            raise RuntimeError("simulated failure for request-id correlation check")

        monkeypatch.setattr("app.routes.users.db.session.get", _boom)

        client.post(
            "/api/v1/auth/register",
            json={"email": "logtest@example.com", "password": "Secure123", "username": "logtest"},
        )
        login_resp = client.post(
            "/api/v1/auth/login", json={"email": "logtest@example.com", "password": "Secure123"}
        )
        token = login_resp.get_json()["data"]["access_token"]

        # app.logger has propagate=False (configure_logging) specifically to
        # avoid double/default Flask logging output, so caplog's own
        # root-logger handler won't see anything by default — attach it
        # directly to app.logger for this one request.
        app.logger.addHandler(caplog.handler)
        try:
            with caplog.at_level(logging.INFO, logger=app.logger.name):
                resp = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token}"})
        finally:
            app.logger.removeHandler(caplog.handler)

        assert resp.status_code == 500
        request_id = resp.headers.get("X-Request-ID")
        assert request_id
        # At least one record emitted during this request carries the same
        # request_id the client actually received.
        assert any(getattr(r, "request_id", None) == request_id for r in caplog.records)


class TestJsonFormatter:
    def test_produces_valid_json_with_expected_fields(self):
        from app.logging_config import _JsonFormatter, _RequestContextFilter

        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="hello %s",
            args=("world",),
            exc_info=None,
        )
        _RequestContextFilter().filter(record)
        formatted = _JsonFormatter().format(record)

        payload = json.loads(formatted)  # must not raise
        assert payload["message"] == "hello world"
        assert payload["level"] == "INFO"
        assert payload["request_id"] == "-"  # no app context active here
        assert payload["user_id"] == "-"
        assert "timestamp" in payload
