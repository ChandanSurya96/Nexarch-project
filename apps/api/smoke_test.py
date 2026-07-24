"""
Standalone smoke test — runs the full auth + /me flow using the Flask test client.
No external server, database, or Docker needed.
Exits 0 on success, 1 on any failure.
"""
import json
import os
import sys

os.environ["DATABASE_URL"] = "sqlite:///smoke_test.db"
os.environ["JWT_SECRET"] = "smoke-test-secret-key-32chars-ok!"
os.environ["FLASK_ENV"] = "development"

from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402

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

print()
if FAIL:
    print("SMOKE TEST: FAILED")
    sys.exit(1)
else:
    print("SMOKE TEST: ALL CHECKS PASSED")
    sys.exit(0)
