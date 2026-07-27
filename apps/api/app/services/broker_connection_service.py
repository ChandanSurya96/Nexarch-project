"""Broker-connection business logic — init, callback, list, disconnect, sync.

See docs/broker-integrations.md "Auth Flow" and docs/product-requirements.md
"Feature: Broker Connection" for the acceptance criteria this implements.
"""

from __future__ import annotations

import json
import os
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.exc import IntegrityError

from app.extensions import db, redis_client
from app.integrations.broker.base import BrokerAuthError
from app.integrations.broker.registry import UnsupportedBrokerError, get_adapter
from app.models.broker_connection import BrokerConnection
from app.services import audit_service
from app.services.encryption_service import encrypt_token

# Cooldown for the manual "sync now" endpoint (see docs/api.md "Rate Limiting"
# — this endpoint has its own tighter limit, separate from general API rate
# limiting). Reuses last_synced_at rather than adding a dedicated column for
# tracking manual-sync requests, since it achieves the same practical gate
# without extra schema surface (see docs/database.md's own "don't add unused
# schema surface area" design principle).
MANUAL_SYNC_COOLDOWN_SECONDS = 300

# How long an in-flight OAuth connect attempt has to complete before its
# state token expires (ADR-023) — generous enough for a real broker login,
# short enough that an abandoned attempt doesn't linger.
OAUTH_STATE_TTL_SECONDS = 600
_OAUTH_STATE_KEY_PREFIX = "oauth_state:"


class BrokerConnectionError(Exception):
    def __init__(self, code: str, message: str, status: int) -> None:
        self.code = code
        self.message = message
        self.status = status
        super().__init__(message)


def _redirect_uri_for(broker_name: str) -> str:
    env_var = f"{broker_name.upper()}_REDIRECT_URI"
    redirect_uri = os.environ.get(env_var, "")
    if not redirect_uri:
        raise BrokerConnectionError("BROKER_NOT_CONFIGURED", f"{env_var} is not configured.", 500)
    return redirect_uri


def init_connection(user_id: uuid.UUID, broker_name: str) -> str:
    """Return the broker login URL for the frontend to redirect the user to.

    Generates a single-use `state` token (ADR-023) and stores it in Redis,
    keyed to this user and broker, so handle_callback can verify the redirect
    that comes back wasn't tampered with or replayed against a different
    session before exchanging the auth code.
    """
    try:
        adapter = get_adapter(broker_name)
    except UnsupportedBrokerError as exc:
        raise BrokerConnectionError("UNSUPPORTED_BROKER", str(exc), 400) from exc

    state = secrets.token_urlsafe(32)
    redis_client.set(
        f"{_OAUTH_STATE_KEY_PREFIX}{state}",
        json.dumps({"user_id": str(user_id), "broker_name": broker_name}),
        ex=OAUTH_STATE_TTL_SECONDS,
    )

    return adapter.get_login_url(_redirect_uri_for(broker_name), state)


def _consume_oauth_state(user_id: uuid.UUID, broker_name: str, state: str) -> None:
    """Verify `state` was the one issued to this user for this broker, then
    delete it — single-use, per the OAuth2 `state` convention.

    Raises BrokerConnectionError(INVALID_OAUTH_STATE) if the state is
    missing, expired, or doesn't match this user/broker — this is exactly
    the CSRF/replay protection a bare auth-code exchange doesn't have.
    """
    key = f"{_OAUTH_STATE_KEY_PREFIX}{state}"
    stored = redis_client.get(key)
    if stored is None:
        raise BrokerConnectionError(
            "INVALID_OAUTH_STATE",
            "This connection request has expired or is invalid. Please try connecting again.",
            400,
        )

    payload = json.loads(stored)
    redis_client.delete(key)  # single-use regardless of outcome

    if payload.get("user_id") != str(user_id) or payload.get("broker_name") != broker_name:
        raise BrokerConnectionError(
            "INVALID_OAUTH_STATE",
            "This connection request has expired or is invalid. Please try connecting again.",
            400,
        )


def handle_callback(
    user_id: uuid.UUID, broker_name: str, auth_code: str, state: str
) -> BrokerConnection:
    """Exchange the auth code, store the connection, and queue the initial sync.

    Per docs/product-requirements.md: the initial sync must be queued within
    seconds of a successful callback, not left for the next scheduled run.

    Reconnecting the same broker (e.g. after an expired token) updates the
    existing connection in place rather than inserting a second row for the
    same (user_id, broker_name) — a second row would have no Portfolio linked
    yet, and its first sync would create a *duplicate* Portfolio for a user
    who already has one, silently splitting their holdings/history across two
    identities (see ADR-021).
    """
    _consume_oauth_state(user_id, broker_name, state)

    try:
        adapter = get_adapter(broker_name)
    except UnsupportedBrokerError as exc:
        raise BrokerConnectionError("UNSUPPORTED_BROKER", str(exc), 400) from exc

    try:
        tokens = adapter.exchange_code(auth_code, _redirect_uri_for(broker_name))
    except BrokerAuthError as exc:
        raise BrokerConnectionError("BROKER_AUTH_FAILED", str(exc), 400) from exc

    connection = BrokerConnection.query.filter_by(user_id=user_id, broker_name=broker_name).first()
    is_new = connection is None
    if connection is None:
        connection = BrokerConnection(
            user_id=user_id, broker_name=broker_name, connection_method="broker_api"
        )
        db.session.add(connection)

    connection.access_token_encrypted = encrypt_token(tokens.access_token)
    connection.refresh_token_encrypted = (
        encrypt_token(tokens.refresh_token) if tokens.refresh_token else None
    )
    connection.status = "active"
    connection.token_expires_at = tokens.expires_at

    try:
        db.session.commit()
    except IntegrityError as exc:
        # broker_connections.user_id is unique (ADR-033): only reachable here
        # when two concurrent first-time-connect requests for this user both
        # passed the is_new check above before either committed. Converts
        # what would otherwise be a duplicate row (or a raw 500) into the
        # same clean error a sibling app-level guard raises for this class
        # of race (see ADR-030/ADR-033).
        db.session.rollback()
        raise BrokerConnectionError(
            "BROKER_ALREADY_CONNECTED",
            "You already have a broker connection. Disconnect it before connecting a different one.",
            409,
        ) from exc

    audit_service.log_event(
        user_id,
        "connect" if is_new else "reconnect",
        {"broker_connection_id": str(connection.id)},
    )

    # Queue immediately — not the next scheduled beat run.
    from app.tasks.sync import sync_portfolio_task

    sync_portfolio_task.delay(str(connection.id))

    return connection


def list_connections(user_id: uuid.UUID) -> list[BrokerConnection]:
    return BrokerConnection.query.filter_by(user_id=user_id).all()


def _get_owned_connection(user_id: uuid.UUID, connection_id: uuid.UUID) -> BrokerConnection:
    connection = db.session.get(BrokerConnection, connection_id)
    if connection is None or connection.user_id != user_id:
        raise BrokerConnectionError(
            "BROKER_CONNECTION_NOT_FOUND", "Broker connection not found.", 404
        )
    return connection


def disconnect(user_id: uuid.UUID, connection_id: uuid.UUID) -> None:
    """Delete a broker connection.

    Per docs/security.md, the encrypted token is deleted immediately, not
    just deactivated — deleting the row achieves this. The linked Portfolio
    and its Holdings are preserved (broker_connection_id is ON DELETE SET
    NULL, per docs/database.md), matching the "keep, marked stale" half of
    the product-requirements.md acceptance criterion; the explicit
    remove-vs-keep user choice on disconnect is not yet built (frontend/UX
    decision, deferred to the milestone that builds that UI).
    """
    connection = _get_owned_connection(user_id, connection_id)
    db.session.delete(connection)
    db.session.commit()
    audit_service.log_event(user_id, "disconnect", {"broker_connection_id": str(connection_id)})


def trigger_manual_sync(user_id: uuid.UUID, connection_id: uuid.UUID) -> None:
    connection = _get_owned_connection(user_id, connection_id)

    if connection.status == "expired":
        raise BrokerConnectionError(
            "BROKER_CONNECTION_EXPIRED",
            "This broker connection needs to be reconnected.",
            401,
        )

    if connection.last_synced_at is not None:
        # SQLite (tests) round-trips naive datetimes even when a UTC-aware
        # one was stored; Postgres (prod) preserves tzinfo. Normalize so the
        # subtraction below is correct on both (all datetimes here are UTC
        # by convention throughout this codebase).
        last_synced = connection.last_synced_at
        if last_synced.tzinfo is None:
            last_synced = last_synced.replace(tzinfo=UTC)
        elapsed = datetime.now(UTC) - last_synced
        if elapsed < timedelta(seconds=MANUAL_SYNC_COOLDOWN_SECONDS):
            raise BrokerConnectionError(
                "SYNC_COOLDOWN_ACTIVE",
                "Please wait before requesting another sync.",
                429,
            )

    from app.tasks.sync import sync_portfolio_task

    sync_portfolio_task.delay(str(connection.id))
