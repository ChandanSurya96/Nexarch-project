"""Login timing benchmark — account-enumeration check (Phase 2.5 fix slice).

Run from the project root with the apps/api venv active:
    apps/api/venv/Scripts/python.exe scripts/benchmark_login_timing.py
    apps/api/venv/bin/python scripts/benchmark_login_timing.py

Why this exists: POST /auth/login returns an identical body and status for
"no such account" and "wrong password", which looks like enough. It isn't —
the response body is not the only channel. `user is None or not
bcrypt.check_password_hash(...)` short-circuits on `or`, so an unknown email
skipped bcrypt entirely and came back in ~3 ms while a real account paid the
full cost-factor ~340 ms. That gap is an account-enumeration oracle: submit
an address, time the 401, learn whether it is registered.

Measured at the HTTP layer deliberately — the number then includes request
parsing, schema validation and serialisation, i.e. exactly what an attacker
sees, rather than a service-layer figure that flatters the result.

Baseline (before the fix, 2026-07-31, bcrypt rounds 12, n=25):
    unknown email          2.8 ms      known, wrong pass    338.8 ms   → 122x
After:
    unknown email        428.7 ms      known, wrong pass    405.7 ms   → 0.95x

Uses SQLite in-memory via the testing config — no Postgres or Redis needed,
and it never touches the dev database.
"""

import os
import statistics
import sys
import time
from pathlib import Path

# Run from the repo root; the Flask app lives in apps/api.
API_DIR = Path(__file__).resolve().parent.parent / "apps" / "api"
sys.path.insert(0, str(API_DIR))
os.chdir(API_DIR)
os.environ.setdefault("FLASK_ENV", "testing")

from app import create_app  # noqa: E402
from app.extensions import bcrypt, db, limiter  # noqa: E402
from app.models.user import User  # noqa: E402

ITERATIONS = int(os.environ.get("ITERATIONS", 25))
KNOWN_EMAIL = "timing-known@example.test"
PASSWORD = "correct-horse-battery-staple"

app = create_app("testing")

# NOT app.config["RATELIMIT_ENABLED"] = False. Setting that after
# Limiter.init_app() has registered its hooks does nothing to a
# route-decorated @limiter.limit() — the first version of this script did
# exactly that, got 429 on nearly every request, and reported a beautifully
# equal ~1.3 ms across all three scenarios. It was timing the rate limiter.
# The storage is reset per request instead, outside the timed region.

with app.app_context():
    db.create_all()
    if not User.query.filter_by(email=KNOWN_EMAIL).first():
        db.session.add(
            User(
                email=KNOWN_EMAIL,
                username="timinguser",
                password_hash=bcrypt.generate_password_hash(PASSWORD).decode(),
            )
        )
        db.session.commit()

client = app.test_client()


def timed(email: str, password: str) -> tuple[float, int]:
    with app.app_context():
        limiter.reset()
    start = time.perf_counter()
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    elapsed = (time.perf_counter() - start) * 1000
    if resp.status_code == 429:
        raise SystemExit("rate limited — the reset above stopped working; numbers would be junk")
    return elapsed, resp.status_code


SCENARIOS = {
    "unknown email      ": ("timing-nobody@example.test", PASSWORD),
    "known, wrong pass  ": (KNOWN_EMAIL, "wrong-password-entirely"),
    "known, correct pass": (KNOWN_EMAIL, PASSWORD),
}

# Warm up: the first call in a process pays one-off costs — generating the
# dummy hash among them — that would otherwise land on whichever scenario
# happens to run first and read as a timing difference.
for _email, _password in SCENARIOS.values():
    timed(_email, _password)

results = {}
for label, (email, password) in SCENARIOS.items():
    samples, statuses = [], set()
    for _ in range(ITERATIONS):
        ms, status = timed(email, password)
        samples.append(ms)
        statuses.add(status)
    results[label] = (samples, statuses)

print(f"\nbcrypt rounds: {app.config.get('BCRYPT_LOG_ROUNDS', 12)}   n={ITERATIONS}\n")
print(f"{'scenario':<21} {'median':>9} {'mean':>9} {'min':>9} {'max':>9}   status")
print("-" * 74)
for label, (samples, statuses) in results.items():
    print(
        f"{label:<21} {statistics.median(samples):>8.1f}ms {statistics.mean(samples):>8.1f}ms "
        f"{min(samples):>8.1f}ms {max(samples):>8.1f}ms   {sorted(statuses)}"
    )

unknown = statistics.median(results["unknown email      "][0])
wrong = statistics.median(results["known, wrong pass  "][0])
ratio = max(unknown, wrong) / min(unknown, wrong)
print(f"\nenumeration signal (wrong-pass - unknown-email): {wrong - unknown:+.1f} ms")
print(f"ratio: {ratio:.2f}x")
print(
    "\nVERDICT: "
    + (
        "EXPLOITABLE - an unknown email is distinguishable by response time alone."
        if ratio > 3
        else "no usable signal - both paths do the same bcrypt work."
    )
)
