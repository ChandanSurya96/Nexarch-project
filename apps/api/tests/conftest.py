"""pytest fixtures shared across all test modules.

The test suite uses SQLite in-memory so no external database is required to
run tests locally. The production DATABASE_URL (Postgres) is unchanged.
"""

import pytest
from sqlalchemy import event
from sqlalchemy.orm import scoped_session, sessionmaker

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
        engine = _db.engine

        if engine.dialect.name == "sqlite":
            # pysqlite's DBAPI manages its own transaction state under the hood and
            # will silently end the connection-level transaction the `db` fixture
            # relies on for rollback the moment it sees a SAVEPOINT/RELEASE emitted
            # for a nested (app-level commit) transaction, unless its own implicit
            # begin/commit handling is disabled like this. Recommended by the
            # SQLAlchemy docs for exactly this "join a session into an external
            # transaction with SAVEPOINTs" scenario. Postgres's driver doesn't have
            # this quirk, so this only applies when TEST_DATABASE_URL isn't set.
            @event.listens_for(engine, "connect")
            def _sqlite_disable_pysqlite_txn_control(dbapi_connection, connection_record):
                dbapi_connection.isolation_level = None

            @event.listens_for(engine, "begin")
            def _sqlite_emit_explicit_begin(conn):
                conn.exec_driver_sql("BEGIN")

        _db.create_all()
        yield _db
        _db.drop_all()


@pytest.fixture(autouse=True)
def db(app, _db_setup):
    """Wrap each test in a transaction that is rolled back afterward.

    This keeps tests isolated without recreating the schema for every test.
    Each test sees a clean slate because the transaction is never committed.

    Reconfiguring the *existing* ``db.session`` with ``bind=connection`` (the
    standard SQLAlchemy recipe) doesn't work here: Flask-SQLAlchemy 3.x's
    ``Session.get_bind()`` (flask_sqlalchemy/session.py) resolves binds through
    its own ``db.engines`` registry and returns ``engines[None]`` (the real app
    engine) before ever consulting the session's own ``bind`` attribute, so the
    override is silently ignored and application code keeps committing through
    the real engine. Instead, swap out ``db.session`` itself for a plain
    (non-Flask-SQLAlchemy) scoped session bound directly to this connection —
    that class's default ``get_bind()`` isn't overridden, so it honors ``bind``.
    ``join_transaction_mode="create_savepoint"`` means nested
    ``db.session.commit()`` calls from application code only release a
    SAVEPOINT rather than ending the outer transaction we roll back below.
    Model.query also picks this up because it resolves ``cls.__fsa__.session``
    fresh on every access (flask_sqlalchemy/model.py), not a cached reference.
    """
    with app.app_context():
        connection = _db_setup.engine.connect()
        transaction = connection.begin()

        original_session = _db_setup.session
        testing_session_factory = sessionmaker(
            bind=connection, join_transaction_mode="create_savepoint"
        )
        _db_setup.session = scoped_session(testing_session_factory)

        yield _db_setup

        _db_setup.session.remove()
        _db_setup.session = original_session
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
