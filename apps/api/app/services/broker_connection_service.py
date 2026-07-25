"""Broker-connection business logic — init, callback, list, disconnect, sync.

See docs/broker-integrations.md "Auth Flow" and docs/product-requirements.md
"Feature: Broker Connection" for the acceptance criteria this implements.
"""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime, timedelta

from app.extensions import db
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


def init_connection(broker_name: str) -> str:
    """Return the broker login URL for the frontend to redirect the user to."""
    try:
        adapter = get_adapter(broker_name)
    except UnsupportedBrokerError as exc:
        raise BrokerConnectionError("UNSUPPORTED_BROKER", str(exc), 400) from exc

    return adapter.get_login_url(_redirect_uri_for(broker_name))


def handle_callback(user_id: uuid.UUID, broker_name: str, auth_code: str) -> BrokerConnection:
    """Exchange the auth code, store the connection, and queue the initial sync.

    Per docs/product-requirements.md: the initial sync must be queued within
    seconds of a successful callback, not left for the next scheduled run.
    """
    try:
        adapter = get_adapter(broker_name)
    except UnsupportedBrokerError as exc:
        raise BrokerConnectionError("UNSUPPORTED_BROKER", str(exc), 400) from exc

    try:
        tokens = adapter.exchange_code(auth_code, _redirect_uri_for(broker_name))
    except BrokerAuthError as exc:
        raise BrokerConnectionError("BROKER_AUTH_FAILED", str(exc), 400) from exc

    connection = BrokerConnection(
        user_id=user_id,
        broker_name=broker_name,
        connection_method="broker_api",
        access_token_encrypted=encrypt_token(tokens.access_token),
        refresh_token_encrypted=(
            encrypt_token(tokens.refresh_token) if tokens.refresh_token else None
        ),
        status="active",
        token_expires_at=tokens.expires_at,
    )
    db.session.add(connection)
    db.session.commit()

    audit_service.log_event(user_id, "connect", {"broker_connection_id": str(connection.id)})

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
