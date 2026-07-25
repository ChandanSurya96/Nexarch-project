"""Tests for /api/v1/broker-connections/*.

The Upstox adapter's HTTP calls and the Celery sync task are both mocked —
these tests exercise routing/service/DB logic only, per
docs/development-guide.md's "no live credentials, no live broker" testing
strategy (extended here to "no live Celery worker/broker either").

Redis (used for the OAuth `state` token, ADR-023) is faked the same way
test_discovery.py fakes it for the discovery-feed cache — an in-memory dict
standing in for redis_client, no live Redis server needed.
"""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock
from urllib.parse import parse_qs, urlparse

import pytest

from app.extensions import db
from app.integrations.broker.base import BrokerAuthError, TokenPair
from app.integrations.broker.registry import UnsupportedBrokerError
from app.models.broker_connection import BrokerConnection

REGISTER_URL = "/api/v1/auth/register"
LOGIN_URL = "/api/v1/auth/login"
INIT_URL = "/api/v1/broker-connections/init"
CALLBACK_URL = "/api/v1/broker-connections/callback"
LIST_URL = "/api/v1/broker-connections"

VALID_USER = {
    "email": "broker-test@example.com",
    "password": "Secure123",
    "username": "brokeruser",
}


def _register_and_login(client, user=None):
    user = user or VALID_USER
    client.post(REGISTER_URL, json=user)
    resp = client.post(LOGIN_URL, json={"email": user["email"], "password": user["password"]})
    return resp.get_json()["data"]["access_token"]


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _state_from_redirect_url(redirect_url: str) -> str:
    return parse_qs(urlparse(redirect_url).query)["state"][0]


def _init(client, token, broker_name="upstox"):
    return client.post(INIT_URL, json={"broker_name": broker_name}, headers=_auth_header(token))


def _connect_broker(client, token, auth_code="good-code", state=None):
    """Goes through the real init -> callback sequence so the state token
    is always a legitimately-issued one, matching how the frontend actually
    drives this flow."""
    if state is None:
        init_resp = _init(client, token)
        state = _state_from_redirect_url(init_resp.get_json()["data"]["redirect_url"])
    return client.post(
        CALLBACK_URL,
        json={"broker_name": "upstox", "auth_code": auth_code, "state": state},
        headers=_auth_header(token),
    )


class _FakeAdapter:
    def get_login_url(self, redirect_uri, state):
        return f"https://fake-upstox.example/login?redirect_uri={redirect_uri}&state={state}"

    def exchange_code(self, auth_code, redirect_uri):
        if auth_code == "bad-code":
            raise BrokerAuthError("invalid auth code")
        return TokenPair(
            access_token="fake-access-token",
            refresh_token="fake-refresh-token",
            expires_at=datetime.now(UTC) + timedelta(days=1),
        )


def _fake_get_adapter(broker_name):
    if broker_name != "upstox":
        raise UnsupportedBrokerError(f"No adapter registered for broker '{broker_name}'.")
    return _FakeAdapter()


@pytest.fixture(autouse=True)
def fake_redis(monkeypatch):
    store: dict[str, str] = {}
    monkeypatch.setattr("app.services.broker_connection_service.redis_client.get", store.get)

    def _set(key, value, ex=None):
        store[key] = value

    def _delete(key):
        store.pop(key, None)

    monkeypatch.setattr("app.services.broker_connection_service.redis_client.set", _set)
    monkeypatch.setattr("app.services.broker_connection_service.redis_client.delete", _delete)
    return store


@pytest.fixture(autouse=True)
def mock_broker_boundary(monkeypatch):
    """Mock the two external boundaries every test in this file crosses:
    the broker adapter registry and the Celery sync task's .delay()."""
    monkeypatch.setattr("app.services.broker_connection_service.get_adapter", _fake_get_adapter)
    monkeypatch.setenv("UPSTOX_REDIRECT_URI", "http://localhost:3000/broker-callback")
    mock_delay = MagicMock()
    monkeypatch.setattr("app.tasks.sync.sync_portfolio_task.delay", mock_delay)
    return mock_delay


class TestInit:
    def test_init_happy_path(self, client):
        token = _register_and_login(client)
        resp = _init(client, token)
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["error"] is None
        assert "redirect_url" in body["data"]
        assert "state=" in body["data"]["redirect_url"]

    def test_init_unsupported_broker(self, client):
        token = _register_and_login(client)
        resp = _init(client, token, broker_name="not-a-real-broker")
        assert resp.status_code == 400
        assert resp.get_json()["error"]["code"] == "UNSUPPORTED_BROKER"

    def test_init_requires_auth(self, client):
        resp = client.post(INIT_URL, json={"broker_name": "upstox"})
        assert resp.status_code == 401

    def test_init_missing_broker_name(self, client):
        token = _register_and_login(client)
        resp = client.post(INIT_URL, json={}, headers=_auth_header(token))
        assert resp.status_code == 400


class TestCallback:
    def test_callback_happy_path_creates_connection_and_queues_sync(
        self, client, mock_broker_boundary
    ):
        token = _register_and_login(client)
        resp = _connect_broker(client, token)
        assert resp.status_code == 201
        body = resp.get_json()
        assert body["error"] is None
        assert body["data"]["broker_name"] == "upstox"
        assert body["data"]["status"] == "active"
        # No token fields ever serialized to the client (see docs/security.md).
        assert "access_token_encrypted" not in body["data"]
        assert "access_token" not in body["data"]

        # Initial sync queued within seconds of a successful callback.
        mock_broker_boundary.assert_called_once()

    def test_callback_stores_token_encrypted_not_plaintext(self, client):
        token = _register_and_login(client)
        _connect_broker(client, token)
        connection = BrokerConnection.query.first()
        assert connection is not None
        assert connection.access_token_encrypted != "fake-access-token"
        assert "fake-access-token" not in connection.access_token_encrypted

    def test_callback_bad_code_returns_400(self, client):
        token = _register_and_login(client)
        resp = _connect_broker(client, token, auth_code="bad-code")
        assert resp.status_code == 400
        assert resp.get_json()["error"]["code"] == "BROKER_AUTH_FAILED"

    def test_reconnect_updates_existing_connection_in_place(self, client, mock_broker_boundary):
        """A second callback for the same (user, broker) — e.g. reconnecting
        after an expired token — must update the same row, not create a
        second one (ADR-021). A second row would have no Portfolio linked
        yet, and the next sync would create a duplicate Portfolio."""
        token = _register_and_login(client)
        first = _connect_broker(client, token).get_json()["data"]

        first_connection = db.session.get(BrokerConnection, uuid.UUID(first["id"]))
        first_connection.status = "expired"
        db.session.commit()

        second = _connect_broker(client, token).get_json()["data"]

        assert second["id"] == first["id"]
        assert second["status"] == "active"
        assert BrokerConnection.query.filter_by(user_id=first_connection.user_id).count() == 1


class TestOAuthState:
    """ADR-023 — the state token is what stops the callback from accepting
    a tampered-with or replayed redirect."""

    def test_callback_without_a_real_init_is_rejected(self, client):
        token = _register_and_login(client)
        resp = client.post(
            CALLBACK_URL,
            json={"broker_name": "upstox", "auth_code": "good-code", "state": "made-up-state"},
            headers=_auth_header(token),
        )
        assert resp.status_code == 400
        assert resp.get_json()["error"]["code"] == "INVALID_OAUTH_STATE"

    def test_callback_missing_state_field_is_a_validation_error(self, client):
        token = _register_and_login(client)
        resp = client.post(
            CALLBACK_URL,
            json={"broker_name": "upstox", "auth_code": "good-code"},
            headers=_auth_header(token),
        )
        assert resp.status_code == 400
        assert resp.get_json()["error"]["code"] == "VALIDATION_ERROR"

    def test_state_cannot_be_reused(self, client):
        token = _register_and_login(client)
        init_resp = _init(client, token)
        state = _state_from_redirect_url(init_resp.get_json()["data"]["redirect_url"])

        first = _connect_broker(client, token, state=state)
        assert first.status_code == 201

        second = _connect_broker(client, token, state=state)
        assert second.status_code == 400
        assert second.get_json()["error"]["code"] == "INVALID_OAUTH_STATE"

    def test_state_issued_to_a_different_user_is_rejected(self, client):
        token = _register_and_login(client)
        init_resp = _init(client, token)
        state = _state_from_redirect_url(init_resp.get_json()["data"]["redirect_url"])

        other_token = _register_and_login(
            client,
            {
                "email": "other-state-user@example.com",
                "password": "Secure123",
                "username": "otherstateuser",
            },
        )
        resp = client.post(
            CALLBACK_URL,
            json={"broker_name": "upstox", "auth_code": "good-code", "state": state},
            headers=_auth_header(other_token),
        )
        assert resp.status_code == 400
        assert resp.get_json()["error"]["code"] == "INVALID_OAUTH_STATE"


class TestList:
    def test_list_only_returns_callers_own_connections(self, client):
        token = _register_and_login(client)
        _connect_broker(client, token)

        other_token = _register_and_login(
            client,
            {
                "email": "other-broker-test@example.com",
                "password": "Secure123",
                "username": "otherbrokeruser",
            },
        )

        resp = client.get(LIST_URL, headers=_auth_header(other_token))
        assert resp.status_code == 200
        assert resp.get_json()["data"] == []


class TestDisconnect:
    def test_disconnect_deletes_the_row(self, client):
        token = _register_and_login(client)
        callback_resp = _connect_broker(client, token)
        connection_id = callback_resp.get_json()["data"]["id"]

        resp = client.delete(
            f"/api/v1/broker-connections/{connection_id}", headers=_auth_header(token)
        )
        assert resp.status_code == 200
        assert db.session.get(BrokerConnection, uuid.UUID(connection_id)) is None

    def test_disconnect_not_owned_returns_404(self, client):
        token = _register_and_login(client)
        callback_resp = _connect_broker(client, token)
        connection_id = callback_resp.get_json()["data"]["id"]

        other_token = _register_and_login(
            client,
            {"email": "not-owner@example.com", "password": "Secure123", "username": "notowner"},
        )

        resp = client.delete(
            f"/api/v1/broker-connections/{connection_id}", headers=_auth_header(other_token)
        )
        assert resp.status_code == 404


class TestManualSync:
    def test_sync_now_queues_when_no_prior_sync(self, client, mock_broker_boundary):
        token = _register_and_login(client)
        callback_resp = _connect_broker(client, token)
        connection_id = callback_resp.get_json()["data"]["id"]
        mock_broker_boundary.reset_mock()  # clear the call from the callback's initial sync

        resp = client.post(
            f"/api/v1/broker-connections/{connection_id}/sync", headers=_auth_header(token)
        )
        assert resp.status_code == 200
        assert resp.get_json()["data"]["queued"] is True
        mock_broker_boundary.assert_called_once()

    def test_sync_now_blocked_within_cooldown(self, client):
        token = _register_and_login(client)
        callback_resp = _connect_broker(client, token)
        connection_id = callback_resp.get_json()["data"]["id"]

        connection = db.session.get(BrokerConnection, uuid.UUID(connection_id))
        connection.last_synced_at = datetime.now(UTC)
        db.session.commit()

        resp = client.post(
            f"/api/v1/broker-connections/{connection_id}/sync", headers=_auth_header(token)
        )
        assert resp.status_code == 429
        assert resp.get_json()["error"]["code"] == "SYNC_COOLDOWN_ACTIVE"

    def test_sync_now_on_expired_connection_returns_expired_error(self, client):
        token = _register_and_login(client)
        callback_resp = _connect_broker(client, token)
        connection_id = callback_resp.get_json()["data"]["id"]

        connection = db.session.get(BrokerConnection, uuid.UUID(connection_id))
        connection.status = "expired"
        db.session.commit()

        resp = client.post(
            f"/api/v1/broker-connections/{connection_id}/sync", headers=_auth_header(token)
        )
        assert resp.status_code == 401
        assert resp.get_json()["error"]["code"] == "BROKER_CONNECTION_EXPIRED"

    def test_sync_now_not_owned_returns_404(self, client):
        token = _register_and_login(client)
        callback_resp = _connect_broker(client, token)
        connection_id = callback_resp.get_json()["data"]["id"]

        other_token = _register_and_login(
            client,
            {
                "email": "not-owner-sync@example.com",
                "password": "Secure123",
                "username": "notownersync",
            },
        )

        resp = client.post(
            f"/api/v1/broker-connections/{connection_id}/sync", headers=_auth_header(other_token)
        )
        assert resp.status_code == 404
