"""pytest fixtures shared across all test modules.

The test suite uses SQLite in-memory so no external database is required to
run tests locally. The production DATABASE_URL (Postgres) is unchanged.
"""

import pytest

from app import create_app
from app.extensions import db as _db
from app.extensions import limiter as _limiter


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

    Known gap: Flask-SQLAlchemy 3.x's Session.get_bind() looks up
    self._db.engines[None] directly for any query that resolves a mapper,
    ahead of whatever this fixture passes to session.configure(bind=...) —
    including with join_transaction_mode="create_savepoint" set, which was
    tried and confirmed (via a standalone repro script, not just reasoning
    about the source) to NOT contain commits to this transaction the way it
    would for a plain SQLAlchemy Session. So a real db.session.commit() from
    application code still commits for real, and this fixture's rollback()
    below only undoes writes that were never committed (e.g. a test that
    asserts on a pre-commit `db.session.flush()` state). Tests that call
    into services doing their own commit() — which is most of them — get
    away with this because they use per-test-unique emails/ids, so a prior
    test's leaked row never collides. Don't add a test that reuses another
    test's identity/unique key and depends on rollback to isolate it.
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


@pytest.fixture(autouse=True)
def _reset_rate_limits(app):
    """Clear flask-limiter's storage before every test.

    Route-decorated limits (@limiter.limit(...) on login/register) enforce
    unconditionally once Limiter.init_app() has registered its hooks —
    Limiter.enabled only gates the extension's own setup at init time and
    header injection afterward, not per-request enforcement of an explicit
    decorator. Since the app (and therefore the limiter's storage) is a
    single session-scoped instance, without a reset every test's
    register/login calls would keep hitting the SAME bucket — e.g.
    test_broker_connections.py alone calls register/login over a dozen
    times, well past the 10-per-hour/5-per-minute limits, and would 429 on
    ordinary test setup instead of exercising the code path under test.
    """
    with app.app_context():
        _limiter.reset()


@pytest.fixture()
def client(app):
    """Flask test client."""
    return app.test_client()
