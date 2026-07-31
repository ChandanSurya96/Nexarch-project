"""Login must not reveal whether an email is registered.

POST /auth/login returns the same body and status for "no such account" and
"wrong password" — that part was always true. What wasn't: the two paths did
different amounts of work. `user is None or not bcrypt.check_password_hash(...)`
short-circuits on `or`, so an unknown email skipped bcrypt entirely and was
rejected in ~2 ms while a real account cost the full ~245 ms cost-factor
work. Measured, that's a ~120x difference — an account-enumeration oracle
that no amount of identical response bodies hides.

Two layers of test here, deliberately:

  * TestEqualWork asserts the *mechanism* — exactly one bcrypt verification
    per login attempt, whatever the email. Deterministic, fast, and it fails
    for the right reason, naming the short-circuit rather than a stopwatch.
  * TestObservedTiming asserts the *outcome* over the wire, with bounds wide
    enough to survive a loaded CI runner but nowhere near wide enough to let
    a 120x gap through. This is the one that would catch a future change
    that reintroduces the leak by some route the mechanism test doesn't model.
"""

import statistics
import time

import pytest

from app.extensions import bcrypt
from app.extensions import limiter as _limiter
from app.services.auth_service import register_user

PASSWORD = "correct-horse-battery-staple"
UNKNOWN_EMAIL = "definitely-not-registered@example.test"


@pytest.fixture()
def known_user(db):
    """A real registered account, created through the real registration path."""
    return register_user(
        email="timing-known@example.test",
        password=PASSWORD,
        username="timinguser",
    )


def _login(client, email, password):
    """POST /auth/login, clearing the rate limiter first.

    POST /auth/login is capped at 5/minute (ADR-032) and these tests
    deliberately make many more attempts than that. conftest's autouse
    _reset_rate_limits only runs once per test, so the reset has to happen
    per call here — otherwise the timing samples would be measuring how
    fast flask-limiter returns 429, which is both meaningless and equal on
    both paths, i.e. a green test proving nothing.
    """
    _limiter.reset()
    return client.post("/api/v1/auth/login", json={"email": email, "password": password})


class TestEqualWork:
    """One bcrypt verification per attempt, registered email or not."""

    @pytest.fixture(autouse=True)
    def _count_bcrypt_calls(self, monkeypatch):
        self.calls = []
        original = bcrypt.check_password_hash

        def counting(pw_hash, password):
            self.calls.append(pw_hash)
            return original(pw_hash, password)

        monkeypatch.setattr(bcrypt, "check_password_hash", counting)

    def test_unknown_email_still_verifies_a_password(self, client, known_user):
        _login(client, UNKNOWN_EMAIL, PASSWORD)
        assert len(self.calls) == 1, (
            "unknown-email login skipped bcrypt entirely — this is the "
            "short-circuit that makes account enumeration possible"
        )

    def test_wrong_password_verifies_once(self, client, known_user):
        _login(client, known_user.email, "not-the-password")
        assert len(self.calls) == 1

    def test_correct_password_verifies_once(self, client, known_user):
        _login(client, known_user.email, PASSWORD)
        assert len(self.calls) == 1

    def test_unknown_email_verifies_against_a_hash_no_password_matches(self, client, known_user):
        """The dummy hash must be a real bcrypt hash, not a sentinel."""
        _login(client, UNKNOWN_EMAIL, PASSWORD)
        (used_hash,) = self.calls

        assert used_hash.startswith("$2b$"), "dummy hash is not a bcrypt hash"
        assert used_hash != known_user.password_hash, "leaked a real user's hash"
        # The whole point: even the *correct* password for a real account
        # doesn't authenticate against it.
        assert not bcrypt.check_password_hash(used_hash, PASSWORD)

    def test_dummy_hash_uses_the_configured_cost_factor(self, app, client, known_user):
        """A hardcoded hash would keep costing 12 rounds after a config bump."""
        _login(client, UNKNOWN_EMAIL, PASSWORD)
        (used_hash,) = self.calls

        expected_rounds = app.config.get("BCRYPT_LOG_ROUNDS", 12)
        assert int(used_hash.split("$")[2]) == expected_rounds


class TestIdenticalResponses:
    """The response itself must not distinguish the two cases either."""

    def test_unknown_email_and_wrong_password_are_indistinguishable(self, client, known_user):
        unknown = _login(client, UNKNOWN_EMAIL, PASSWORD)
        wrong = _login(client, known_user.email, "not-the-password")

        assert unknown.status_code == wrong.status_code == 401
        assert unknown.get_json() == wrong.get_json()
        assert unknown.get_json()["error"]["code"] == "INVALID_CREDENTIALS"

    def test_correct_credentials_still_succeed(self, client, known_user):
        """Equal work must not come at the cost of login actually working."""
        resp = _login(client, known_user.email, PASSWORD)
        assert resp.status_code == 200
        assert resp.get_json()["data"]["access_token"]


class TestObservedTiming:
    """End-to-end timing, with CI-tolerant bounds."""

    SAMPLES = 5
    # Pre-fix this ratio was ~120. Anything under 3 means bcrypt dominates
    # both paths, which is the property being protected; the bound is loose
    # on purpose so a slow shared runner can't turn this red spuriously.
    MAX_RATIO = 3.0

    def _median_ms(self, client, email, password):
        timings = []
        for _ in range(self.SAMPLES):
            start = time.perf_counter()
            _login(client, email, password)
            timings.append((time.perf_counter() - start) * 1000)
        return statistics.median(timings)

    def test_unknown_email_is_not_measurably_faster(self, client, known_user):
        # Warm up: first request in a process pays one-off costs (the dummy
        # hash generation among them) that would otherwise skew whichever
        # scenario runs first.
        _login(client, UNKNOWN_EMAIL, PASSWORD)
        _login(client, known_user.email, "warmup")

        unknown_ms = self._median_ms(client, UNKNOWN_EMAIL, PASSWORD)
        wrong_ms = self._median_ms(client, known_user.email, "not-the-password")

        ratio = max(unknown_ms, wrong_ms) / min(unknown_ms, wrong_ms)
        assert ratio < self.MAX_RATIO, (
            f"login timing distinguishes registered from unregistered emails: "
            f"unknown={unknown_ms:.1f}ms wrong-password={wrong_ms:.1f}ms "
            f"(ratio {ratio:.1f}x, limit {self.MAX_RATIO}x)"
        )


class TestSingleAuditRecord:
    """Exactly one audit row per successful login.

    Both the route and authenticate_user() logged "login", so every
    successful login wrote two identical rows — silently doubling the
    success side of any failed-vs-successful ratio an incident responder
    computes from this table.
    """

    def _login_events(self, db, user_id):
        from app.models.audit_log import AuditLog

        return AuditLog.query.filter_by(user_id=user_id, event_type="login").all()

    def test_one_row_per_successful_login(self, client, db, known_user):
        assert _login(client, known_user.email, PASSWORD).status_code == 200
        assert len(self._login_events(db, known_user.id)) == 1

    def test_repeat_logins_accumulate_one_each(self, client, db, known_user):
        for _ in range(3):
            assert _login(client, known_user.email, PASSWORD).status_code == 200
        assert len(self._login_events(db, known_user.id)) == 3

    def test_failed_login_writes_no_login_event(self, client, db, known_user):
        assert _login(client, known_user.email, "wrong").status_code == 401
        assert self._login_events(db, known_user.id) == []
