"""Minimal repro proving the `db` fixture rolls back commits from application
code between tests.

Regression test for the leak described in the `db` fixture's docstring in
conftest.py: `auth_service.register_user` calls `db.session.commit()`, and
without the fix that row survived into later tests. Order is deliberate —
the committing test runs first so a fix regression would show up as the
second test's count coming back non-zero. Both tests must also pass when
run alone (`pytest tests/test_db_isolation.py::test_name`), which proves
the leak isn't a same-test-file logic bug.
"""

from app.models.user import User
from app.services.auth_service import register_user


def test_commits_a_user_via_a_real_service_call(app):
    with app.app_context():
        register_user(email="leak-check@example.com", password="Secure123", username="leakcheck")
        assert User.query.filter_by(email="leak-check@example.com").count() == 1


def test_previous_commit_did_not_leak_into_this_test(app):
    with app.app_context():
        assert User.query.count() == 0
