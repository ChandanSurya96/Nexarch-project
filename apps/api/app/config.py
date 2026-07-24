"""App configuration.

Values are read from environment variables (loaded from .env by python-dotenv
in create_app). Defaults are intentionally non-functional so a missing .env
fails loudly rather than silently using insecure placeholders.
"""

import os


class Config:
    # ── Database ──────────────────────────────────────────────────────────────
    SQLALCHEMY_DATABASE_URI: str = os.environ.get("DATABASE_URL", "")
    SQLALCHEMY_TRACK_MODIFICATIONS: bool = False

    # ── JWT ───────────────────────────────────────────────────────────────────
    # flask-jwt-extended uses SECRET_KEY as the signing secret by default.
    SECRET_KEY: str = os.environ.get("JWT_SECRET", "")
    JWT_ACCESS_TOKEN_EXPIRES: int = int(os.environ.get("JWT_ACCESS_TTL_MINUTES", 15)) * 60
    JWT_REFRESH_TOKEN_EXPIRES: int = int(os.environ.get("JWT_REFRESH_TTL_DAYS", 30)) * 24 * 60 * 60
    # Refresh token is stored in a cookie, not the response body (see ADR-004).
    JWT_TOKEN_LOCATION: list[str] = ["headers", "cookies"]
    JWT_COOKIE_SECURE: bool = os.environ.get("FLASK_ENV", "development") != "development"
    JWT_COOKIE_SAMESITE: str = "Lax"
    JWT_COOKIE_CSRF_PROTECT: bool = False  # CSRF protection for cookies — Phase 2 hardening

    # ── Redis ─────────────────────────────────────────────────────────────────
    REDIS_URL: str = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

    # ── Celery ────────────────────────────────────────────────────────────────
    CELERY_BROKER_URL: str = REDIS_URL
    CELERY_RESULT_BACKEND: str = REDIS_URL


class DevelopmentConfig(Config):
    DEBUG: bool = True


class TestingConfig(Config):
    TESTING: bool = True
    # SQLite in-memory by default — no external DB needed to run the test suite.
    # Override with TEST_DATABASE_URL if you want to run tests against Postgres.
    SQLALCHEMY_DATABASE_URI: str = os.environ.get(
        "TEST_DATABASE_URL",
        "sqlite:///:memory:",
    )
    # Must be non-empty; flask-jwt-extended requires SECRET_KEY or JWT_SECRET_KEY.
    SECRET_KEY: str = os.environ.get("JWT_SECRET", "test-only-secret-not-for-production")
    JWT_COOKIE_SECURE: bool = False
    # Use a short-lived access token in tests so expiry edge cases are easy to trigger.
    JWT_ACCESS_TOKEN_EXPIRES: int = 60  # 1 minute


config_map: dict[str, type[Config]] = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": Config,
}
