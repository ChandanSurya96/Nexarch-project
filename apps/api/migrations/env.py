"""Alembic environment configuration.

This file is loaded by Alembic for all migration commands.
It imports the SQLAlchemy metadata from the Flask app so that
`alembic revision --autogenerate` can diff against the real models.
"""

import os
from logging.config import fileConfig

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import engine_from_config, pool

# Load environment variables so DATABASE_URL is available.
load_dotenv()

# Alembic Config object — gives access to .ini file values.
config = context.config

# Override sqlalchemy.url from the environment so we never hard-code
# a database URL in a committed file.
database_url = os.environ.get("DATABASE_URL", "")
if database_url:
    config.set_main_option("sqlalchemy.url", database_url)

# Logging config from alembic.ini (skipped when flask-migrate drives the run,
# because it passes an in-memory config with no associated .ini file).
if config.config_file_name is not None:
    import os as _os

    if _os.path.isfile(config.config_file_name):
        fileConfig(config.config_file_name)

# Import the Flask app's metadata so autogenerate sees all models.
# The app factory is NOT called here — we only need the metadata.
from app.extensions import db  # noqa: E402
import app.models  # noqa: E402, F401 — ensures all models are registered

target_metadata = db.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (no live DB connection needed)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode (live DB connection)."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
