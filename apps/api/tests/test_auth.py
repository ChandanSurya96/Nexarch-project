"""Tests for POST /api/v1/auth/register, /login, /refresh, /logout."""

import pytest


# ─── Helpers ──────────────────────────────────────────────────────────────────

REGISTER_URL = "/api/v1/auth/register"
LOGIN_URL = "/api/v1/auth/login"
REFRESH_URL = "/api/v1/auth/refresh"
LOGOUT_URL = "/api/v1/auth/logout"

VALID_USER = {
    "email": "investor@example.com",
    "password": "Secure123",
    "username": "investor1",
}


def register(client, payload=None):
    return client.post(REGISTER_URL, json=payload or VALID_USER)


def login(client, payload=None):
    return client.post(
        LOGIN_URL,
        json=payload or {"email": VALID_USER["email"], "password": VALID_USER["password"]},
    )


def auth_header(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}"}


# ─── Register ─────────────────────────────────────────────────────────────────


class TestRegister:
    def test_register_happy_path(self, client):
        resp = register(client)
        assert resp.status_code == 201
        body = resp.get_json()
        assert body["error"] is None
        assert body["data"]["email"] == VALID_USER["email"]
        assert body["data"]["username"] == VALID_USER["username"]
        assert "user_id" in body["data"]
        # password_hash must never appear in the response
        assert "password" not in body["data"]
        assert "password_hash" not in body["data"]

    def test_register_duplicate_email(self, client):
        register(client)
        resp = register(client)
        assert resp.status_code == 409
        assert resp.get_json()["error"]["code"] == "EMAIL_TAKEN"

    def test_register_duplicate_username(self, client):
        register(client)
        resp = client.post(
            REGISTER_URL,
            json={
                "email": "different@example.com",
                "password": "Secure123",
                "username": VALID_USER["username"],
            },
        )
        assert resp.status_code == 409
        assert resp.get_json()["error"]["code"] == "USERNAME_TAKEN"

    def test_register_missing_field(self, client):
        resp = client.post(REGISTER_URL, json={"email": "a@b.com", "password": "Secure123"})
        assert resp.status_code == 400
        assert resp.get_json()["error"]["code"] == "VALIDATION_ERROR"

    def test_register_invalid_email(self, client):
        resp = client.post(
            REGISTER_URL,
            json={"email": "not-an-email", "password": "Secure123", "username": "u1"},
        )
        assert resp.status_code == 400

    def test_register_weak_password(self, client):
        # All letters, no digit — should fail the strength check.
        resp = client.post(
            REGISTER_URL,
            json={"email": "x@example.com", "password": "onlyletters", "username": "usrx"},
        )
        assert resp.status_code == 400

    def test_register_short_password(self, client):
        resp = client.post(
            REGISTER_URL,
            json={"email": "x@example.com", "password": "Ab1", "username": "usrx"},
        )
        assert resp.status_code == 400

    def test_register_invalid_username_chars(self, client):
        resp = client.post(
            REGISTER_URL,
            json={"email": "x@example.com", "password": "Secure123", "username": "bad user!"},
        )
        assert resp.status_code == 400


# ─── Login ────────────────────────────────────────────────────────────────────


class TestLogin:
    def test_login_happy_path(self, client):
        register(client)
        resp = login(client)
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["error"] is None
        # Access token in the body.
        assert "access_token" in body["data"]
        # Refresh token must be in a cookie, NOT in the body.
        assert "refresh_token" not in body["data"]
        assert any("refresh_token" in c for c in resp.headers.getlist("Set-Cookie"))

    def test_login_wrong_password(self, client):
        register(client)
        resp = client.post(LOGIN_URL, json={"email": VALID_USER["email"], "password": "Wrong999"})
        assert resp.status_code == 401
        assert resp.get_json()["error"]["code"] == "INVALID_CREDENTIALS"

    def test_login_unknown_email(self, client):
        resp = client.post(LOGIN_URL, json={"email": "nobody@example.com", "password": "Secure123"})
        assert resp.status_code == 401
        # Same error code for unknown email and wrong password (timing-safe).
        assert resp.get_json()["error"]["code"] == "INVALID_CREDENTIALS"

    def test_login_missing_field(self, client):
        resp = client.post(LOGIN_URL, json={"email": VALID_USER["email"]})
        assert resp.status_code == 400


# ─── Refresh ──────────────────────────────────────────────────────────────────


class TestRefresh:
    def test_refresh_happy_path(self, client):
        register(client)
        login_resp = login(client)
        # The test client stores cookies automatically; /refresh reads the cookie.
        resp = client.post(REFRESH_URL)
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["error"] is None
        assert "access_token" in body["data"]
        # Refresh cookie should be rotated.
        assert any("refresh_token" in c for c in resp.headers.getlist("Set-Cookie"))

    def test_refresh_without_cookie(self, client):
        # No login → no cookie → should 401.
        resp = client.post(REFRESH_URL)
        assert resp.status_code == 401

    def test_refresh_with_tampered_cookie(self, client):
        client.set_cookie("refresh_token_cookie", "this.is.garbage")
        resp = client.post(REFRESH_URL)
        assert resp.status_code == 422  # flask-jwt-extended returns 422 for malformed tokens


# ─── Logout ───────────────────────────────────────────────────────────────────


class TestLogout:
    def test_logout_happy_path(self, client):
        register(client)
        login_resp = login(client)
        access_token = login_resp.get_json()["data"]["access_token"]

        resp = client.post(LOGOUT_URL, headers=auth_header(access_token))
        assert resp.status_code == 200
        # Refresh cookie should be cleared (Max-Age=0 or Expires in the past).
        set_cookie_headers = resp.headers.getlist("Set-Cookie")
        refresh_cleared = any(
            "refresh_token" in c and ("Max-Age=0" in c or "expires" in c.lower())
            for c in set_cookie_headers
        )
        assert refresh_cleared

    def test_logout_without_access_token(self, client):
        resp = client.post(LOGOUT_URL)
        assert resp.status_code == 401
