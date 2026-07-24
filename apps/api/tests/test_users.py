"""Tests for GET /api/v1/users/me."""

import pytest

REGISTER_URL = "/api/v1/auth/register"
LOGIN_URL = "/api/v1/auth/login"
ME_URL = "/api/v1/users/me"

VALID_USER = {
    "email": "metest@example.com",
    "password": "Secure123",
    "username": "meuser",
}


def _register_and_login(client):
    client.post(REGISTER_URL, json=VALID_USER)
    resp = client.post(
        LOGIN_URL,
        json={"email": VALID_USER["email"], "password": VALID_USER["password"]},
    )
    return resp.get_json()["data"]["access_token"]


class TestGetMe:
    def test_get_me_happy_path(self, client):
        token = _register_and_login(client)
        resp = client.get(ME_URL, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["error"] is None
        data = body["data"]
        assert data["email"] == VALID_USER["email"]
        assert data["username"] == VALID_USER["username"]
        # Sensitive fields must not be exposed.
        assert "password_hash" not in data
        assert "password" not in data
        # Expected shape
        assert "id" in data
        assert "is_public" in data
        assert "created_at" in data

    def test_get_me_no_token(self, client):
        resp = client.get(ME_URL)
        assert resp.status_code == 401

    def test_get_me_invalid_token(self, client):
        resp = client.get(ME_URL, headers={"Authorization": "Bearer not.a.real.token"})
        assert resp.status_code == 422
