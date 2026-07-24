"""Auth service — business logic for registration and authentication.

No Flask imports here. This layer is pure Python so it's testable without
a running Flask app (just needs the extensions objects via the app context).

See docs/architecture.md for the routes → services → models layering rationale.
"""

from __future__ import annotations

from app.extensions import bcrypt, db
from app.models.user import User


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
            leaking whether a given email is registered.
    """
    email = email.lower().strip()
    user = User.query.filter_by(email=email).first()

    if user is None or not bcrypt.check_password_hash(user.password_hash, password):
        raise AuthError("INVALID_CREDENTIALS", "Invalid email or password.", 401)

    return user
