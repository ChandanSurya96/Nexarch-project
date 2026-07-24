"""pytest fixtures shared across all test modules.

The test suite uses SQLite in-memory so no external database is required to
run tests locally. The production DATABASE_URL (Postgres) is unchanged.
"""

import pytest

from app import create_app
from app.extensions import db as _db


@pytest.fixture(scope="session")
def app():
    """Create a test Flask app with the testing config (SQLite in-memory)."""
    application = create_app("testing")
    return application


@pytest.fixture(scope="session")
def _db_setup(app):
    """Create all tables once per test session; drop them at teardown."""
    with app.app_context():
        _db.create_all()
        yield _db
        _db.drop_all()


@pytest.fixture(autouse=True)
def db(app, _db_setup):
    """Wrap each test in a transaction that is rolled back afterward.

    This keeps tests isolated without recreating the schema for every test.
    Each test sees a clean slate because the transaction is never committed.
    """
    with app.app_context():
        connection = _db_setup.engine.connect()
        transaction = connection.begin()
        # Bind the session to this connection so everything uses the same transaction.
        _db_setup.session.configure(bind=connection)

        yield _db_setup

        _db_setup.session.remove()
        transaction.rollback()
        connection.close()


@pytest.fixture()
def client(app):
    """Flask test client."""
    return app.test_client()
