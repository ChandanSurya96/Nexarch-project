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
    # CSRF protection for the refresh-token cookie (ADR-031) — only ever
    # actually gates POST /auth/refresh in practice, since the access token
    # only ever travels via the Authorization header (ADR-017), never a
    # cookie, and flask-jwt-extended only checks CSRF for cookie-sourced tokens.
    JWT_COOKIE_CSRF_PROTECT: bool = True

    # ── Redis ─────────────────────────────────────────────────────────────────
    REDIS_URL: str = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

    # ── Celery ────────────────────────────────────────────────────────────────
    CELERY_BROKER_URL: str = REDIS_URL
    CELERY_RESULT_BACKEND: str = REDIS_URL

    # ── Historical prices (ADR-037) ───────────────────────────────────────────
    # Concurrency for the sync worker's per-instrument price fetches. Kept
    # deliberately low: these are outbound broker calls, and staying well
    # under any broker's rate limit matters more than shaving sync latency.
    HISTORICAL_PRICE_CONCURRENCY: int = int(os.environ.get("HISTORICAL_PRICE_CONCURRENCY", 4))
    # Past daily closes are immutable, so a long TTL is safe; a day keeps the
    # cache useful across syncs without pinning stale data indefinitely.
    HISTORICAL_PRICE_CACHE_TTL_SECONDS: int = int(
        os.environ.get("HISTORICAL_PRICE_CACHE_TTL_SECONDS", 24 * 60 * 60)
    )

    # ── Rate limiting (ADR-032) ─────────────────────────────────────────────────
    RATELIMIT_STORAGE_URI: str = REDIS_URL
    RATELIMIT_HEADERS_ENABLED: bool = True
    RATELIMIT_ENABLED: bool = True


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
    # CSRF stays enabled in tests (inherited True from Config) — disabling it
    # for tests would mean this protection ships with zero coverage.
    # RATELIMIT_ENABLED stays True (inherited from Config) — real enforcement
    # runs in tests too; tests/conftest.py resets the limiter's storage before
    # every test so cross-test accumulation doesn't trip limits meant for
    # real traffic (see that fixture's docstring for why — route-decorated
    # limits enforce unconditionally once registered, regardless of
    # Limiter.enabled, which only gates setup-at-init-time and headers).
    # In-memory, not the real Redis (see docs/development-guide.md "no live
    # external dependency" testing philosophy) — flask-limiter's own storage
    # is independent of app/extensions.py's redis_client wrapper, so faking
    # that wrapper alone (as other tests do) wouldn't isolate this.
    RATELIMIT_STORAGE_URI: str = "memory://"


config_map: dict[str, type[Config]] = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": Config,
}
