"""App factory.

Usage:
    from app import create_app
    app = create_app()          # reads FLASK_ENV from environment
    app = create_app("testing") # explicit config name
"""

import os

from dotenv import load_dotenv
from flask import Flask

from app.extensions import bcrypt, db, jwt, migrate, redis_client


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

    # ── Bind extensions ───────────────────────────────────────────────────────
    db.init_app(app)
    jwt.init_app(app)
    bcrypt.init_app(app)
    migrate.init_app(app, db)
    redis_client.init_app(app)

    # ── Register blueprints ───────────────────────────────────────────────────
    from app.routes.auth import auth_bp
    from app.routes.broker_connections import broker_connections_bp
    from app.routes.discovery import discovery_bp
    from app.routes.portfolios import portfolios_bp
    from app.routes.public_investors import public_investors_bp
    from app.routes.users import users_bp

    app.register_blueprint(auth_bp, url_prefix="/api/v1/auth")
    app.register_blueprint(users_bp, url_prefix="/api/v1/users")
    app.register_blueprint(broker_connections_bp, url_prefix="/api/v1/broker-connections")
    app.register_blueprint(portfolios_bp, url_prefix="/api/v1/portfolios")
    app.register_blueprint(discovery_bp, url_prefix="/api/v1/discovery")
    app.register_blueprint(public_investors_bp, url_prefix="/api/v1/public-investors")

    return app
