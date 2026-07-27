"""Refresh-token rotation with reuse detection (ADR-030).

Each login starts a "family" — a random id (`fid`) embedded as a custom
claim in both the access and refresh token. Redis tracks the current valid
`jti` for that family. Rotating (POST /auth/refresh) issues a new pair with
the same `fid` and advances the tracked jti. Presenting a refresh token
whose jti doesn't match the currently-tracked one — and isn't the
immediately-previous one, within a short grace window — is theft-shaped
reuse: the whole family is killed, forcing a real re-login.

Family-based, not a single global per-user lock, so concurrent device
sessions (phone + desktop) don't invalidate each other — reuse only kills
the one family the stolen token belonged to.

Grace window (10s): two legitimate concurrent /refresh calls from the SAME
session (e.g. two browser tabs, both firing AuthProvider's silent-refresh
near-simultaneously) is normal, expected behavior for this app, not an
attack. Without a short grace window on the immediately-previous jti, that
ordinary race would force a real re-login with no attacker involved — the
same reuse-interval pattern real-world providers (Auth0, Cognito) use for
exactly this scenario.
"""

from __future__ import annotations

import secrets

from flask import current_app
from flask_jwt_extended import create_access_token, create_refresh_token, decode_token

from app.extensions import redis_client

_FAMILY_KEY_PREFIX = "refresh_family:"
_PREV_SUFFIX = ":prev"
_GRACE_WINDOW_SECONDS = 10


class RefreshSessionInvalidError(Exception):
    """The family key is missing entirely — natural TTL expiry, or already
    killed by a prior reuse-detection event."""


class RefreshReuseError(Exception):
    """A refresh token was presented whose jti doesn't match the current
    or recently-previous one for its family — a real reuse signal."""


def _family_key(family_id: str) -> str:
    return f"{_FAMILY_KEY_PREFIX}{family_id}"


def _prev_key(family_id: str) -> str:
    return f"{_FAMILY_KEY_PREFIX}{family_id}{_PREV_SUFFIX}"


def _refresh_ttl_seconds() -> int:
    return int(current_app.config["JWT_REFRESH_TOKEN_EXPIRES"])


def _issue_pair(identity: str, family_id: str) -> tuple[str, str, str]:
    """Returns (access_token, refresh_token, new_refresh_jti)."""
    access_token = create_access_token(identity=identity, additional_claims={"fid": family_id})
    refresh_token = create_refresh_token(identity=identity, additional_claims={"fid": family_id})
    new_jti = decode_token(refresh_token)["jti"]
    return access_token, refresh_token, new_jti


def issue_new_family(identity: str) -> tuple[str, str]:
    """Start a new refresh-token family at login."""
    family_id = secrets.token_urlsafe(16)
    access_token, refresh_token, jti = _issue_pair(identity, family_id)
    redis_client.set(_family_key(family_id), jti, ex=_refresh_ttl_seconds())
    return access_token, refresh_token


def rotate(identity: str, family_id: str, incoming_jti: str) -> tuple[str, str]:
    """Rotate a refresh token, keeping the same family.

    Raises RefreshSessionInvalidError if the family has naturally expired or
    was already killed. Raises RefreshReuseError if incoming_jti is neither
    the current nor the recently-previous jti for this family (real reuse).
    """
    current_jti = redis_client.get(_family_key(family_id))
    if current_jti is None:
        raise RefreshSessionInvalidError("This session has expired. Please log in again.")

    if incoming_jti != current_jti:
        prev_jti = redis_client.get(_prev_key(family_id))
        if prev_jti is None or incoming_jti != prev_jti:
            # Real reuse: neither the current nor the recently-superseded
            # jti — kill the whole family rather than just rejecting this call.
            redis_client.delete(_family_key(family_id))
            redis_client.delete(_prev_key(family_id))
            raise RefreshReuseError(
                "This refresh token has already been used. All sessions in this "
                "family have been revoked for safety."
            )
        # Else: incoming_jti matches the immediately-previous one — a benign
        # concurrent-tab race, not theft. Fall through and rotate normally.

    access_token, refresh_token, new_jti = _issue_pair(identity, family_id)
    redis_client.set(_prev_key(family_id), current_jti, ex=_GRACE_WINDOW_SECONDS)
    redis_client.set(_family_key(family_id), new_jti, ex=_refresh_ttl_seconds())
    return access_token, refresh_token


def kill_family(family_id: str) -> None:
    """Revoke a family immediately — called on logout."""
    redis_client.delete(_family_key(family_id))
    redis_client.delete(_prev_key(family_id))
