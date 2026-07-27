"""Tests for app/error_handlers.py (ADR-029).

Every failure mode — JWT rejection, unmatched route, unhandled exception —
must return the documented envelope: {"data": null, "meta": {}, "error":
{"code", "message", "status"}}, not flask-jwt-extended's or Flask's own
un-enveloped default response.
"""

from datetime import timedelta

from flask_jwt_extended import create_access_token


def _register_and_login(client, email="error-handler-test@example.com"):
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "Secure123", "username": email.split("@")[0]},
    )
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": "Secure123"})
    return resp.get_json()["data"]["access_token"]


def _envelope_ok(body: dict) -> bool:
    return set(body.keys()) == {"data", "meta", "error"} and body["data"] is None


class TestMissingOrMalformedToken:
    def test_missing_token_on_required_route(self, client):
        resp = client.get("/api/v1/users/me")
        assert resp.status_code == 401
        body = resp.get_json()
        assert _envelope_ok(body)
        assert body["error"]["code"] == "AUTHORIZATION_REQUIRED"

    def test_malformed_token(self, client):
        resp = client.get(
            "/api/v1/users/me", headers={"Authorization": "Bearer not-a-real-jwt-at-all"}
        )
        assert resp.status_code == 422
        body = resp.get_json()
        assert _envelope_ok(body)
        assert body["error"]["code"] == "TOKEN_INVALID"


class TestExpiredToken:
    def test_expired_access_token(self, client, app):
        with app.app_context():
            token = create_access_token(
                identity="00000000-0000-0000-0000-000000000000", expires_delta=timedelta(seconds=-1)
            )

        resp = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 401
        body = resp.get_json()
        assert _envelope_ok(body)
        assert body["error"]["code"] == "ACCESS_TOKEN_EXPIRED"


class TestUnmatchedRoutes:
    def test_404_on_unknown_path(self, client):
        resp = client.get("/api/v1/this-route-does-not-exist")
        assert resp.status_code == 404
        body = resp.get_json()
        assert _envelope_ok(body)
        assert body["error"]["code"] == "NOT_FOUND"

    def test_405_on_wrong_method(self, client):
        # GET /api/v1/users/me only supports GET/PATCH, not DELETE.
        resp = client.delete("/api/v1/users/me")
        assert resp.status_code == 405
        body = resp.get_json()
        assert _envelope_ok(body)
        assert body["error"]["code"] == "METHOD_NOT_ALLOWED"


class TestUnhandledException:
    def test_internal_error_returns_generic_envelope_without_leaking_details(
        self, client, monkeypatch
    ):
        token = _register_and_login(client)

        def _boom(*args, **kwargs):
            raise RuntimeError("some sensitive internal detail that must never reach a client")

        monkeypatch.setattr("app.routes.users.db.session.get", _boom)

        resp = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 500
        body = resp.get_json()
        assert _envelope_ok(body)
        assert body["error"]["code"] == "INTERNAL_SERVER_ERROR"
        assert "sensitive internal detail" not in body["error"]["message"]
