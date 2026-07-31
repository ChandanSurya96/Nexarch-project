"""Auth service — business logic for registration and authentication.

No Flask imports here. This layer is pure Python so it's testable without
a running Flask app (just needs the extensions objects via the app context).

See docs/architecture.md for the routes → services → models layering rationale.
"""

from __future__ import annotations

import secrets

from app.extensions import bcrypt, db
from app.models.user import User
from app.services import audit_service

# Cached per process; see _dummy_password_hash().
_DUMMY_PASSWORD_HASH: str | None = None


def _dummy_password_hash() -> str:
    """A bcrypt hash that no submitted password can ever match.

    Used to give the unknown-email login path the same bcrypt cost as the
    wrong-password path (see authenticate_user). Generated lazily rather
    than at import because flask-bcrypt reads its cost factor from
    current_app.config, which doesn't exist at import time — and deriving
    it from the app's own config is the point: a hardcoded hash would keep
    costing 12 rounds after someone raised BCRYPT_LOG_ROUNDS to 13, quietly
    reopening the timing gap this closes.

    The input is random per process and immediately discarded, so there is
    no value an attacker could submit that verifies against it.
    """
    global _DUMMY_PASSWORD_HASH
    if _DUMMY_PASSWORD_HASH is None:
        # A racing thread computing this twice is harmless — both results
        # are equally unmatchable, and the assignment itself is atomic.
        _DUMMY_PASSWORD_HASH = bcrypt.generate_password_hash(secrets.token_urlsafe(32)).decode(
            "utf-8"
        )
    return _DUMMY_PASSWORD_HASH


class AuthError(Exception):
    """Raised for auth-domain errors; routes map these to HTTP responses."""

    def __init__(self, code: str, message: str, status: int = 400) -> None:
        self.code = code
        self.message = message
        self.status = status
        super().__init__(message)


def register_user(email: str, password: str, username: str) -> User:
    """Create a new user.

    Args:
        email: Must be unique.
        username: Must be unique; 3–50 chars, letters/digits/underscores/hyphens.
        password: Plain-text; hashed before storage.

    Returns:
        The newly created User instance (already flushed to the session).

    Raises:
        AuthError: EMAIL_TAKEN if email already registered.
        AuthError: USERNAME_TAKEN if username already taken.
    """
    email = email.lower().strip()
    username = username.strip()

    if User.query.filter_by(email=email).first():
        raise AuthError("EMAIL_TAKEN", "An account with this email already exists.", 409)

    if User.query.filter_by(username=username).first():
        raise AuthError("USERNAME_TAKEN", "This username is already taken.", 409)

    password_hash = bcrypt.generate_password_hash(password).decode("utf-8")
    user = User(email=email, username=username, password_hash=password_hash)
    db.session.add(user)
    db.session.commit()
    return user


def authenticate_user(email: str, password: str) -> User:
    """Verify credentials and return the User.

    Args:
        email: The email address to look up.
        password: Plain-text password to verify against the stored hash.

    Returns:
        The authenticated User instance.

    Raises:
        AuthError: INVALID_CREDENTIALS if email not found or password wrong.
            Deliberately uses the same error code for both cases to avoid
            leaking whether a given email is registered — and, since the
            response body alone isn't the whole channel, the same amount of
            bcrypt work too (see below).
    """
    email = email.lower().strip()
    user = User.query.filter_by(email=email).first()

    # Always perform exactly one bcrypt verification, including when the
    # email is unknown. The natural spelling of this check —
    #   `if user is None or not bcrypt.check_password_hash(...)`
    # — short-circuits on `or`, so an unknown email skips bcrypt entirely
    # and is rejected in a few milliseconds while a real account costs the
    # full cost-factor work. That difference is a reliable account
    # enumeration oracle: measured 2.8 ms vs 338.8 ms before this change
    # (122x), a gap far too wide to hide in network noise. Verifying
    # against a throwaway hash costs the same work and cannot succeed.
    # scripts/benchmark_login_timing.py reproduces both numbers.
    password_hash = user.password_hash if user is not None else _dummy_password_hash()
    password_matches = bcrypt.check_password_hash(password_hash, password)

    if user is None or not password_matches:
        raise AuthError("INVALID_CREDENTIALS", "Invalid email or password.", 401)

    # This is the only place a successful login is audit-logged. Routes must
    # not log it as well — POST /auth/login did until this was fixed, writing
    # two identical rows per login and inflating any "failed vs successful
    # login" ratio an incident responder would compute from this table.
    audit_service.log_event(user.id, "login")
    return user
