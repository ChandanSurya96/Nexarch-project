"""App factory.

Usage:
    from app import create_app
    app = create_app()          # reads FLASK_ENV from environment
    app = create_app("testing") # explicit config name
"""

import os
import secrets

from dotenv import load_dotenv
from flask import Flask, g

from app.extensions import bcrypt, db, jwt, limiter, migrate, redis_client
from app.logging_config import configure_logging


def create_app(config_name: str | None = None) -> Flask:
    """Create and configure the Flask application."""
    load_dotenv()  # must run before importing app.config, below

    # Imported here rather than at module level so .env is guaranteed loaded
    # first: Config's class attributes (e.g. SQLALCHEMY_DATABASE_URI =
    # os.environ.get("DATABASE_URL", "")) are evaluated once, at
    # class-definition time — the first moment app.config is imported. A
    # module-level import here would run before load_dotenv() on any entry
    # point that doesn't pre-populate the environment itself (this is exactly
    # what tripped up app/celery_app.py — TestingConfig's sqlite default
    # masked the issue for pytest, and smoke_test.py/Flask's own CLI both
    # happen to set the relevant env vars before ever importing this module).
    from app.config import config_map

    if config_name is None:
        config_name = os.environ.get("FLASK_ENV", "development")

    app = Flask(__name__)
    app.config.from_object(config_map[config_name])

    # ── Structured logging (ADR-034) ──────────────────────────────────────────
    configure_logging(app)

    # ── Bind extensions ───────────────────────────────────────────────────────
    db.init_app(app)
    jwt.init_app(app)
    bcrypt.init_app(app)
    migrate.init_app(app, db)
    redis_client.init_app(app)
    limiter.init_app(app)

    # ── Request correlation id (ADR-034) ──────────────────────────────────────
    @app.before_request
    def _set_request_id():
        g.request_id = secrets.token_hex(8)
        # Best-effort — most routes are public or use optional JWT, so this
        # isn't always resolvable, and that's fine (logging.g.get(...) falls
        # back to "-"). Avoids importing this at module level to keep
        # app/logging_config.py's filter decoupled from JWT specifics.
        from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request

        try:
            verify_jwt_in_request(optional=True)
            g.user_id = get_jwt_identity()
        except Exception:
            g.user_id = None

    @app.after_request
    def _echo_request_id(response):
        response.headers["X-Request-ID"] = g.get("request_id", "-")
        return response

    # ── Register blueprints ───────────────────────────────────────────────────
    from app.routes.auth import auth_bp
    from app.routes.broker_connections import broker_connections_bp
    from app.routes.discovery import discovery_bp
    from app.routes.health import health_bp
    from app.routes.portfolios import portfolios_bp
    from app.routes.public_investors import public_investors_bp
    from app.routes.users import users_bp

    app.register_blueprint(health_bp)
    app.register_blueprint(auth_bp, url_prefix="/api/v1/auth")
    app.register_blueprint(users_bp, url_prefix="/api/v1/users")
    app.register_blueprint(broker_connections_bp, url_prefix="/api/v1/broker-connections")
    app.register_blueprint(portfolios_bp, url_prefix="/api/v1/portfolios")
    app.register_blueprint(discovery_bp, url_prefix="/api/v1/discovery")
    app.register_blueprint(public_investors_bp, url_prefix="/api/v1/public-investors")

    # ── Error handling (ADR-029) ───────────────────────────────────────────────
    from app.error_handlers import register_error_handlers

    register_error_handlers(app)

    return app
