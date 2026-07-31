"""Fail-fast configuration validation (ADR-039).

Runs once in create_app(). In production, refuses to start the app when a
security-critical setting is missing, empty, or obviously a placeholder.

This exists because the opposite was true and silently dangerous. Before
this module, `SECRET_KEY = os.environ.get("JWT_SECRET", "")` meant a
production deploy with `JWT_SECRET` unset would start cleanly, report
healthy on /health and /health/ready, and issue JWTs signed with the empty
string — which anyone aware of the default could forge for *any* user id.
A complete authentication bypass with no error anywhere. Verified against
the real app before this was written, not theorised.

config.py's docstring had claimed "defaults are intentionally non-functional
so a missing .env fails loudly"; that was aspirational. This module makes it
true, following the precedent already set by
app/services/encryption_service._master_secret(), which does raise on a
missing ENCRYPTION_KMS_KEY_ID.

Deliberately production-only: development and testing keep their working
defaults (SQLite, a fixed test secret) so local setup and the test suite
don't need real secrets. That's the same environment split config.py
already uses.
"""

from __future__ import annotations

from flask import Flask

# Long enough that a short, guessable, or truncated value is rejected. Not a
# strength guarantee — it's a floor that catches the realistic failure modes
# (empty, "changeme", a copy-pasted placeholder), not an entropy check.
_MIN_SECRET_LENGTH = 32

# Values that are clearly not real secrets. Matched case-insensitively against
# the whole value; a real generated secret won't equal any of these.
_PLACEHOLDER_VALUES = {
    "",
    "changeme",
    "change-me",
    "secret",
    "password",
    "test",
    "dev",
    "development",
    "placeholder",
    "your-secret-here",
    "todo",
    "xxx",
    "test-only-secret-not-for-production",
}


class ConfigurationError(Exception):
    """Raised at startup when production configuration is unsafe.

    Deliberately fatal: a misconfigured production app should fail to boot
    loudly rather than serve traffic in an insecure state.
    """


def _require(name: str, value: str | None, problems: list[str]) -> None:
    if value is None or not str(value).strip():
        problems.append(f"{name} is not set (or is empty).")


def _require_strong_secret(name: str, value: str | None, problems: list[str]) -> None:
    if value is None or not str(value).strip():
        problems.append(f"{name} is not set (or is empty).")
        return
    candidate = str(value).strip()
    if candidate.lower() in _PLACEHOLDER_VALUES:
        problems.append(f"{name} is set to a placeholder value.")
    elif len(candidate) < _MIN_SECRET_LENGTH:
        problems.append(
            f"{name} is shorter than {_MIN_SECRET_LENGTH} characters — "
            'generate one with `python -c "import secrets; print(secrets.token_urlsafe(48))"`.'
        )


def validate_production_config(app: Flask) -> None:
    """Raise ConfigurationError if this production app is unsafe to run.

    Collects *every* problem before raising rather than failing on the first,
    so an operator fixing a bad deploy sees the full list in one pass instead
    of rediscovering them one restart at a time.
    """
    problems: list[str] = []

    # Signs every JWT. An empty/weak value here is a full auth bypass.
    _require_strong_secret("JWT_SECRET", app.config.get("SECRET_KEY"), problems)

    # Wraps the per-record data keys protecting broker access tokens — the
    # highest-sensitivity data Nexarch stores (docs/security.md).
    _require_strong_secret(
        "ENCRYPTION_KMS_KEY_ID", app.config.get("ENCRYPTION_KMS_KEY_ID"), problems
    )

    _require("DATABASE_URL", app.config.get("SQLALCHEMY_DATABASE_URI"), problems)
    _require("REDIS_URL", app.config.get("REDIS_URL"), problems)

    # A localhost Redis in production is almost always an unset variable
    # falling through to the development default rather than a deliberate
    # choice — and it fails silently (rate limits and the refresh-token
    # family store just don't work) rather than loudly.
    redis_url = str(app.config.get("REDIS_URL") or "")
    if "localhost" in redis_url or "127.0.0.1" in redis_url:
        problems.append(
            "REDIS_URL points at localhost in production — this is the development "
            "default, which means the variable was probably never set."
        )

    if problems:
        raise ConfigurationError(
            "Refusing to start: production configuration is unsafe.\n  - "
            + "\n  - ".join(problems)
            + "\nSee docs/operations.md for the required environment variables."
        )
