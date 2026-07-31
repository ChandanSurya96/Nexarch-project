"""Tests for app/config_validation.py (ADR-039).

The regression these exist to prevent is specific and was real: before this
validation, `create_app("production")` with JWT_SECRET unset started
successfully and issued JWTs signed with the empty string — forgeable for any
user id, with both health endpoints reporting green. See
test_empty_jwt_secret_is_rejected below, which is that exact scenario.
"""

from __future__ import annotations

import pytest
from flask import Flask

from app.config_validation import ConfigurationError, validate_production_config


def _prod_app(**overrides) -> Flask:
    """A Flask app carrying a *valid* production config, minus any overrides.

    Starting from valid and breaking one thing per test keeps each test about
    one failure mode rather than asserting on a pile of unrelated problems.
    """
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY="a-real-generated-secret-value-long-enough-to-pass",
        ENCRYPTION_KMS_KEY_ID="another-real-generated-secret-long-enough",
        SQLALCHEMY_DATABASE_URI="postgresql://user:pw@db.example.com:5432/nexarch",
        REDIS_URL="redis://cache.example.com:6379/0",
    )
    app.config.update(overrides)
    return app


class TestAcceptsValidConfig:
    def test_fully_configured_production_app_passes(self):
        validate_production_config(_prod_app())  # must not raise


class TestJwtSecret:
    def test_empty_jwt_secret_is_rejected(self):
        """The original vulnerability: empty signing secret -> forgeable tokens."""
        with pytest.raises(ConfigurationError) as exc:
            validate_production_config(_prod_app(SECRET_KEY=""))
        assert "JWT_SECRET" in str(exc.value)

    def test_placeholder_jwt_secret_is_rejected(self):
        with pytest.raises(ConfigurationError) as exc:
            validate_production_config(_prod_app(SECRET_KEY="changeme"))
        assert "placeholder" in str(exc.value)

    def test_the_testing_config_secret_is_rejected_in_production(self):
        """TestingConfig's fixed secret is public in the repo — it must never
        be what a production deploy ends up running with."""
        with pytest.raises(ConfigurationError):
            validate_production_config(_prod_app(SECRET_KEY="test-only-secret-not-for-production"))

    def test_short_secret_is_rejected(self):
        with pytest.raises(ConfigurationError) as exc:
            validate_production_config(_prod_app(SECRET_KEY="abc123"))
        assert "shorter than" in str(exc.value)


class TestOtherRequiredSettings:
    def test_missing_encryption_key_is_rejected(self):
        with pytest.raises(ConfigurationError) as exc:
            validate_production_config(_prod_app(ENCRYPTION_KMS_KEY_ID=""))
        assert "ENCRYPTION_KMS_KEY_ID" in str(exc.value)

    def test_missing_database_url_is_rejected(self):
        with pytest.raises(ConfigurationError) as exc:
            validate_production_config(_prod_app(SQLALCHEMY_DATABASE_URI=""))
        assert "DATABASE_URL" in str(exc.value)

    def test_localhost_redis_is_rejected(self):
        """Almost always an unset variable falling through to the dev default,
        and it fails silently (rate limits and refresh-token families just
        stop working) rather than loudly."""
        with pytest.raises(ConfigurationError) as exc:
            validate_production_config(_prod_app(REDIS_URL="redis://localhost:6379/0"))
        assert "localhost" in str(exc.value)


class TestErrorReporting:
    def test_every_problem_is_reported_at_once(self):
        """An operator fixing a bad deploy should see the full list in one
        pass, not rediscover problems one restart at a time."""
        with pytest.raises(ConfigurationError) as exc:
            validate_production_config(
                _prod_app(SECRET_KEY="", ENCRYPTION_KMS_KEY_ID="", SQLALCHEMY_DATABASE_URI="")
            )
        message = str(exc.value)
        assert "JWT_SECRET" in message
        assert "ENCRYPTION_KMS_KEY_ID" in message
        assert "DATABASE_URL" in message


class TestNonProductionUnaffected:
    def test_testing_config_still_builds_without_real_secrets(self):
        """Dev/testing must keep working with no real secrets — otherwise
        every contributor and CI run needs production credentials."""
        from app import create_app

        app = create_app("testing")
        assert app.config["TESTING"] is True
