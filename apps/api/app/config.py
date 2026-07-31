"""App configuration.

Values are read from environment variables (loaded from .env by python-dotenv
in create_app).

Defaults here are permissive so local development and the test suite work
without real secrets. They are NOT safe for production — which is exactly why
app/config_validation.py runs at startup and refuses to boot a production app
whose security-critical settings are missing, empty, or placeholders
(ADR-039). An earlier version of this docstring claimed these defaults were
"intentionally non-functional so a missing .env fails loudly"; they weren't,
and nothing failed — a production app with JWT_SECRET unset started happily
and signed tokens with the empty string. Validation is what makes the claim
true, so don't rely on the defaults below to protect anything.
"""

import os


class Config:
    # ── Database ──────────────────────────────────────────────────────────────
    SQLALCHEMY_DATABASE_URI: str = os.environ.get("DATABASE_URL", "")
    SQLALCHEMY_TRACK_MODIFICATIONS: bool = False

    # ── Encryption (docs/security.md, ADR-014) ────────────────────────────────
    # Master secret wrapping the per-record data keys that protect broker
    # tokens. Surfaced in config (not just read via os.environ inside
    # encryption_service) so startup validation can check it before any
    # request runs, rather than discovering it on the first sync.
    ENCRYPTION_KMS_KEY_ID: str = os.environ.get("ENCRYPTION_KMS_KEY_ID", "")
    # Multi-key form used during a rotation: "1:<secret>,2:<secret>" (ADR-044).
    # Optional — with only ENCRYPTION_KMS_KEY_ID set, that key is version 1 and
    # is active, which is exactly the pre-ADR-044 behaviour. encryption_service
    # reads these from os.environ directly (it runs in worker threads with no
    # app context); they are mirrored here so startup validation can see them.
    ENCRYPTION_KEYS: str = os.environ.get("ENCRYPTION_KEYS", "")
    # Which version new tokens are wrapped with. Defaults to the highest
    # configured version when unset.
    ENCRYPTION_ACTIVE_KEY_VERSION: str = os.environ.get("ENCRYPTION_ACTIVE_KEY_VERSION", "")

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

    # ── Error tracking (ADR-041) ──────────────────────────────────────────────
    # Unset by default in every environment. app/monitoring.py is a complete
    # no-op without a DSN, so nothing is sent anywhere until an operator opts
    # in — local dev and CI never talk to Sentry.
    SENTRY_DSN: str = os.environ.get("SENTRY_DSN", "")
    SENTRY_ENVIRONMENT: str = os.environ.get("SENTRY_ENVIRONMENT", "production")
    # Set by the deploy pipeline (git SHA) so an event points at a build.
    APP_RELEASE: str = os.environ.get("APP_RELEASE", "")
    # Performance tracing off by default — errors are the value here; tracing
    # is a paid-plan concern to enable deliberately, not a silent default.
    SENTRY_TRACES_SAMPLE_RATE: float = float(os.environ.get("SENTRY_TRACES_SAMPLE_RATE", 0.0))

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

    # ── Scheduled sync fan-out (ADR-046) ──────────────────────────────────────
    # The daily sync is spread across this window instead of firing every
    # connection at 02:00:00 sharp. Broker rate limits are per-application,
    # so the herd grows with total users, not per-user activity.
    SYNC_WINDOW_MINUTES: int = int(os.environ.get("SYNC_WINDOW_MINUTES", 120))
    # Upper bound on how many syncs may start close together.
    SYNC_BATCH_SIZE: int = int(os.environ.get("SYNC_BATCH_SIZE", 20))

    # ── Sync monitoring thresholds (ADR-047) ──────────────────────────────────
    # Read by GET /health/sync. Defaults assume the daily 02:00 schedule:
    # 26h gives a full cycle plus the fan-out window plus slack, so a single
    # late run doesn't page anyone but a genuinely missed day does.
    SYNC_SCHEDULER_MAX_AGE_HOURS: int = int(os.environ.get("SYNC_SCHEDULER_MAX_AGE_HOURS", 26))
    SYNC_WORKER_MAX_AGE_HOURS: int = int(os.environ.get("SYNC_WORKER_MAX_AGE_HOURS", 26))
    # Two missed days before this fires — one bad night is a broker problem,
    # two is ours.
    SYNC_SUCCESS_MAX_AGE_HOURS: int = int(os.environ.get("SYNC_SUCCESS_MAX_AGE_HOURS", 50))
    # Fraction of connections stuck in "error" that counts as unhealthy.
    # Some individual failures are normal (a user revoked access); half of
    # them failing is not.
    SYNC_MAX_ERROR_RATIO: float = float(os.environ.get("SYNC_MAX_ERROR_RATIO", 0.5))

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
