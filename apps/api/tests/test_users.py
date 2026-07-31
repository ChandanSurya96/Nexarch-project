"""Tests for GET /api/v1/users/me."""

import uuid

from app.extensions import db
from app.models.portfolio import Portfolio

REGISTER_URL = "/api/v1/auth/register"
LOGIN_URL = "/api/v1/auth/login"
ME_URL = "/api/v1/users/me"
MY_PORTFOLIO_URL = "/api/v1/users/me/portfolio"

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


class TestGetMyPortfolio:
    def test_no_portfolio_yet_returns_null_not_404(self, client):
        """A brand-new signup has no Portfolio row yet (ADR-019) — this is a
        normal state, not an error."""
        token = _register_and_login(client)
        resp = client.get(MY_PORTFOLIO_URL, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["error"] is None
        assert body["data"] is None

    def test_returns_the_callers_own_portfolio(self, client):
        token = _register_and_login(client)
        resp = client.get(ME_URL, headers={"Authorization": f"Bearer {token}"})
        user_id = uuid.UUID(resp.get_json()["data"]["id"])
        portfolio = Portfolio(user_id=user_id, portfolio_type="verified")
        db.session.add(portfolio)
        db.session.commit()

        resp = client.get(MY_PORTFOLIO_URL, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data["id"] == str(portfolio.id)

    def test_no_token(self, client):
        resp = client.get(MY_PORTFOLIO_URL)
        assert resp.status_code == 401
