"""
Standalone smoke test — runs the full auth + /me flow, plus the Milestone 2
broker-connect -> sync -> analytics flow, using the Flask test client.
No external server, database, or Docker needed (the broker adapter and the
Celery task's .delay() are mocked, same as the pytest suite).
Exits 0 on success, 1 on any failure.
"""
import os
import sys
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

os.environ["DATABASE_URL"] = "sqlite:///smoke_test.db"
os.environ["JWT_SECRET"] = "smoke-test-secret-key-32chars-ok!"
os.environ["ENCRYPTION_KMS_KEY_ID"] = "smoke-test-master-secret-not-for-production"
os.environ["UPSTOX_REDIRECT_URI"] = "http://localhost:3000/broker-callback"
os.environ["FLASK_ENV"] = "development"

from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402
from app.integrations.broker.base import RawHolding, TokenPair  # noqa: E402

app = create_app("development")

FAIL = False


def check(label, condition, detail=""):
    global FAIL
    status = "PASS" if condition else "FAIL"
    print(f"  [{status}] {label}", f"({detail})" if detail else "")
    if not condition:
        FAIL = True


with app.app_context():
    db.create_all()

with app.test_client() as c:
    # ── REGISTER ─────────────────────────────────────────────────────────────
    print("\n=== REGISTER ===")
    r = c.post(
        "/api/v1/auth/register",
        json={"email": "smoke@example.com", "password": "Smoke123", "username": "smokeuser"},
    )
    body = r.get_json()
    check("status 201", r.status_code == 201, r.status_code)
    check("error is None", body["error"] is None, body.get("error"))
    check("data.email", body["data"]["email"] == "smoke@example.com")
    check("data.username", body["data"]["username"] == "smokeuser")
    check("no password in response", "password_hash" not in body["data"])
    user_id = body["data"]["user_id"]
    check("user_id present", bool(user_id), user_id)
    print(f"  user_id = {user_id}")

    # ── LOGIN ─────────────────────────────────────────────────────────────────
    print("\n=== LOGIN ===")
    r = c.post(
        "/api/v1/auth/login",
        json={"email": "smoke@example.com", "password": "Smoke123"},
    )
    body = r.get_json()
    check("status 200", r.status_code == 200, r.status_code)
    check("error is None", body["error"] is None, body.get("error"))
    access_token = body["data"].get("access_token", "")
    check("access_token in body", bool(access_token))
    check("refresh_token NOT in body", "refresh_token" not in body["data"])

    # Check refresh token is in a cookie
    set_cookie = r.headers.get("Set-Cookie", "")
    check("refresh cookie set", "refresh_token_cookie" in set_cookie)

    # Extract cookie value for subsequent requests
    refresh_cookie = next(
        (h for h in r.headers.getlist("Set-Cookie") if "refresh_token_cookie" in h), ""
    )
    cookie_val = refresh_cookie.split(";")[0].split("=", 1)[1] if "=" in refresh_cookie else ""
    print(f"  access_token  = {access_token[:40]}...")
    print(f"  refresh cookie present = {'refresh_token_cookie' in set_cookie}")

    # ── GET /me ───────────────────────────────────────────────────────────────
    print("\n=== GET /me ===")
    r = c.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    body = r.get_json()
    check("status 200", r.status_code == 200, r.status_code)
    check("error is None", body["error"] is None, body.get("error"))
    check("data.id matches", body["data"]["id"] == user_id, body["data"].get("id"))
    check("data.email", body["data"]["email"] == "smoke@example.com")
    check("no password_hash", "password_hash" not in body["data"])
    check("is_public present", "is_public" in body["data"])

    # ── REFRESH ───────────────────────────────────────────────────────────────
    print("\n=== REFRESH ===")
    c.set_cookie("refresh_token_cookie", cookie_val)
    r = c.post("/api/v1/auth/refresh")
    body = r.get_json()
    check("status 200", r.status_code == 200, r.status_code)
    check("error is None", body["error"] is None, body.get("error"))
    new_access_token = body["data"].get("access_token", "")
    check("new access_token in body", bool(new_access_token))
    check("new access_token differs", new_access_token != access_token)

    # ── LOGOUT ────────────────────────────────────────────────────────────────
    print("\n=== LOGOUT ===")
    r = c.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {new_access_token}"},
    )
    body = r.get_json()
    check("status 200", r.status_code == 200, r.status_code)
    check("error is None", body["error"] is None, body.get("error"))
    logout_cookies = " ".join(r.headers.getlist("Set-Cookie"))
    check(
        "refresh cookie cleared (Expires=epoch or Max-Age=0)",
        "Max-Age=0" in logout_cookies
        or "max-age=0" in logout_cookies
        or "01 Jan 1970" in logout_cookies,
        repr(logout_cookies[:80]),
    )

    # ── BROKER CONNECT -> SYNC -> ANALYTICS (Milestone 2) ───────────────────────
    print("\n=== BROKER CONNECT ===")

    class _FakeAdapter:
        def get_login_url(self, redirect_uri):
            return f"https://fake-upstox.example/login?redirect_uri={redirect_uri}"

        def exchange_code(self, auth_code, redirect_uri):
            return TokenPair(
                access_token="fake-access-token",
                refresh_token="fake-refresh-token",
                expires_at=datetime.now(UTC) + timedelta(days=1),
            )

        def fetch_holdings(self, access_token):
            return [
                RawHolding(
                    symbol="RELIANCE",
                    isin="INE002A01018",
                    exchange="NSE",
                    quantity=10.0,
                    avg_cost_price=2500.0,
                )
            ]

    # Re-login since the previous access token was minted before this point
    # (re-using it is fine too, but this mirrors a fresh authenticated session).
    with (
        patch(
            "app.services.broker_connection_service.get_adapter",
            return_value=_FakeAdapter(),
        ),
        patch(
            "app.services.sync_service.get_adapter",
            return_value=_FakeAdapter(),
        ),
        patch("app.tasks.sync.sync_portfolio_task.delay") as mock_delay,
    ):
        r = c.post(
            "/api/v1/broker-connections/init",
            json={"broker_name": "upstox"},
            headers={"Authorization": f"Bearer {new_access_token}"},
        )
        body = r.get_json()
        check("init status 200", r.status_code == 200, r.status_code)
        check("init redirect_url present", "redirect_url" in body["data"])

        r = c.post(
            "/api/v1/broker-connections/callback",
            json={"broker_name": "upstox", "auth_code": "good-code"},
            headers={"Authorization": f"Bearer {new_access_token}"},
        )
        body = r.get_json()
        check("callback status 201", r.status_code == 201, r.status_code)
        check("callback status active", body["data"]["status"] == "active")
        check("initial sync queued", mock_delay.called)
        connection_id = body["data"]["id"]
        print(f"  broker_connection_id = {connection_id}")

        # Run the sync synchronously (simulating what the Celery worker would
        # do) so the smoke test exercises the full normalize/analytics path
        # without needing a live Redis broker or worker process. Explicit
        # app context since this bypasses the test client (which pushes its
        # own context only around actual requests).
        from app.services.sync_service import run_sync

        with app.app_context():
            run_sync(connection_id)

    print("\n=== PORTFOLIOS / ANALYTICS ===")
    r = c.get(
        "/api/v1/broker-connections",
        headers={"Authorization": f"Bearer {new_access_token}"},
    )
    body = r.get_json()
    check("list status 200", r.status_code == 200)
    check("connection synced", body["data"][0]["last_synced_at"] is not None)

    import uuid as _uuid

    from app.models.portfolio import Portfolio

    with app.app_context():
        portfolio = Portfolio.query.filter_by(user_id=_uuid.UUID(user_id)).first()
        portfolio_id = portfolio.id if portfolio is not None else None
    check("portfolio created by sync", portfolio_id is not None)

    # Portfolio defaults to private (is_public=False, per ADR-011) — the
    # owner's token is required to view it before the toggle below.
    auth = {"Authorization": f"Bearer {new_access_token}"}

    r = c.get(f"/api/v1/portfolios/{portfolio_id}/holdings", headers=auth)
    body = r.get_json()
    check("holdings status 200", r.status_code == 200, r.status_code)
    check("one holding synced", len(body["data"]) == 1, len(body["data"]))
    check("holding symbol", body["data"][0]["symbol"] == "RELIANCE")
    check("sector enriched", body["data"][0]["sector"] == "Energy")

    r = c.get(f"/api/v1/portfolios/{portfolio_id}/analytics", headers=auth)
    body = r.get_json()
    check("analytics status 200", r.status_code == 200, r.status_code)
    check("hhi is 1.0 for single holding", body["data"]["health"]["sector_concentration_hhi"] == 1.0)
    check("no composite score field", "score" not in body["data"]["health"])
    check("no volatility field", "volatility" not in body["data"]["health"])

    print("\n=== PUBLIC/PRIVATE TOGGLE ===")
    r = c.patch(
        f"/api/v1/portfolios/{portfolio_id}",
        json={"is_public": True},
        headers={"Authorization": f"Bearer {new_access_token}"},
    )
    body = r.get_json()
    check("patch status 200", r.status_code == 200)
    check("is_public toggled", body["data"]["is_public"] is True)

print()
if FAIL:
    print("SMOKE TEST: FAILED")
    sys.exit(1)
else:
    print("SMOKE TEST: ALL CHECKS PASSED")
    sys.exit(0)
