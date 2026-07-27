"""Tests for POST /api/v1/auth/register, /login, /refresh, /logout."""

# ─── Helpers ──────────────────────────────────────────────────────────────────

REGISTER_URL = "/api/v1/auth/register"
LOGIN_URL = "/api/v1/auth/login"
REFRESH_URL = "/api/v1/auth/refresh"
LOGOUT_URL = "/api/v1/auth/logout"

VALID_USER = {
    "email": "investor@example.com",
    "password": "Secure123",
    "username": "investor1",
}


def register(client, payload=None):
    return client.post(REGISTER_URL, json=payload or VALID_USER)


def login(client, payload=None):
    return client.post(
        LOGIN_URL,
        json=payload or {"email": VALID_USER["email"], "password": VALID_USER["password"]},
    )


def auth_header(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}"}


def csrf_header(client) -> dict:
    """The refresh-token cookie flow requires the CSRF double-submit header
    (ADR-031) — read the non-httpOnly CSRF cookie flask-jwt-extended sets
    alongside the refresh cookie and send it back as X-CSRF-TOKEN."""
    cookie = client.get_cookie("csrf_refresh_token")
    return {"X-CSRF-TOKEN": cookie.value} if cookie else {}


# ─── Register ─────────────────────────────────────────────────────────────────


class TestRegister:
    def test_register_happy_path(self, client):
        resp = register(client)
        assert resp.status_code == 201
        body = resp.get_json()
        assert body["error"] is None
        assert body["data"]["email"] == VALID_USER["email"]
        assert body["data"]["username"] == VALID_USER["username"]
        assert "user_id" in body["data"]
        # password_hash must never appear in the response
        assert "password" not in body["data"]
        assert "password_hash" not in body["data"]

    def test_register_duplicate_email(self, client):
        register(client)
        resp = register(client)
        assert resp.status_code == 409
        assert resp.get_json()["error"]["code"] == "EMAIL_TAKEN"

    def test_register_duplicate_username(self, client):
        register(client)
        resp = client.post(
            REGISTER_URL,
            json={
                "email": "different@example.com",
                "password": "Secure123",
                "username": VALID_USER["username"],
            },
        )
        assert resp.status_code == 409
        assert resp.get_json()["error"]["code"] == "USERNAME_TAKEN"

    def test_register_missing_field(self, client):
        resp = client.post(REGISTER_URL, json={"email": "a@b.com", "password": "Secure123"})
        assert resp.status_code == 400
        assert resp.get_json()["error"]["code"] == "VALIDATION_ERROR"

    def test_register_invalid_email(self, client):
        resp = client.post(
            REGISTER_URL,
            json={"email": "not-an-email", "password": "Secure123", "username": "u1"},
        )
        assert resp.status_code == 400

    def test_register_weak_password(self, client):
        # All letters, no digit — should fail the strength check.
        resp = client.post(
            REGISTER_URL,
            json={"email": "x@example.com", "password": "onlyletters", "username": "usrx"},
        )
        assert resp.status_code == 400

    def test_register_short_password(self, client):
        resp = client.post(
            REGISTER_URL,
            json={"email": "x@example.com", "password": "Ab1", "username": "usrx"},
        )
        assert resp.status_code == 400

    def test_register_invalid_username_chars(self, client):
        resp = client.post(
            REGISTER_URL,
            json={"email": "x@example.com", "password": "Secure123", "username": "bad user!"},
        )
        assert resp.status_code == 400


# ─── Login ────────────────────────────────────────────────────────────────────


class TestLogin:
    def test_login_happy_path(self, client):
        register(client)
        resp = login(client)
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["error"] is None
        # Access token in the body.
        assert "access_token" in body["data"]
        # Refresh token must be in a cookie, NOT in the body.
        assert "refresh_token" not in body["data"]
        assert any("refresh_token" in c for c in resp.headers.getlist("Set-Cookie"))

    def test_login_wrong_password(self, client):
        register(client)
        resp = client.post(LOGIN_URL, json={"email": VALID_USER["email"], "password": "Wrong999"})
        assert resp.status_code == 401
        assert resp.get_json()["error"]["code"] == "INVALID_CREDENTIALS"

    def test_login_unknown_email(self, client):
        resp = client.post(LOGIN_URL, json={"email": "nobody@example.com", "password": "Secure123"})
        assert resp.status_code == 401
        # Same error code for unknown email and wrong password (timing-safe).
        assert resp.get_json()["error"]["code"] == "INVALID_CREDENTIALS"

    def test_login_missing_field(self, client):
        resp = client.post(LOGIN_URL, json={"email": VALID_USER["email"]})
        assert resp.status_code == 400


# ─── Refresh ──────────────────────────────────────────────────────────────────


class TestRefresh:
    def test_refresh_happy_path(self, client):
        register(client)
        login(client)
        # The test client stores cookies automatically; /refresh reads the cookie.
        resp = client.post(REFRESH_URL, headers=csrf_header(client))
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["error"] is None
        assert "access_token" in body["data"]
        # Refresh cookie should be rotated.
        assert any("refresh_token" in c for c in resp.headers.getlist("Set-Cookie"))

    def test_refresh_without_cookie(self, client):
        # No login → no cookie → should 401.
        resp = client.post(REFRESH_URL)
        assert resp.status_code == 401

    def test_refresh_missing_csrf_header_is_rejected(self, client):
        # ADR-031 — a valid refresh cookie with no CSRF header must be rejected,
        # not silently accepted.
        register(client)
        login(client)
        resp = client.post(REFRESH_URL)  # no X-CSRF-TOKEN
        assert resp.status_code == 401
        assert resp.get_json()["error"]["code"] == "CSRF_TOKEN_MISSING"

    def test_refresh_with_tampered_cookie(self, client):
        client.set_cookie("refresh_token_cookie", "this.is.garbage")
        # A CSRF header of any value — CSRF is checked before the cookie
        # itself is decoded, so without one this would 401 on the CSRF check
        # rather than exercising the tampered-token path this test targets.
        resp = client.post(REFRESH_URL, headers={"X-CSRF-TOKEN": "whatever"})
        assert resp.status_code == 422  # flask-jwt-extended returns 422 for malformed tokens
        assert resp.get_json()["error"]["code"] == "TOKEN_INVALID"

    def test_refresh_rotation_updates_the_family(self, client):
        register(client)
        login(client)
        first_refresh = client.post(REFRESH_URL, headers=csrf_header(client))
        assert first_refresh.status_code == 200
        # Rotating again with the new cookie must also succeed.
        second_refresh = client.post(REFRESH_URL, headers=csrf_header(client))
        assert second_refresh.status_code == 200

    def test_reused_refresh_token_is_rejected_and_kills_the_family(self, client):
        """ADR-030 — presenting a refresh token that's neither the current
        nor the immediately-previous one (genuinely stale, not a benign
        concurrent-tab race) is theft-shaped reuse: rejected, and the
        *current* valid token stops working too, not just this request."""
        register(client)
        login(client)
        # jti0: the original token from login.
        jti0_cookie = client.get_cookie("refresh_token_cookie").value
        jti0_csrf = csrf_header(client)

        # Rotate twice — jti0 is now neither current (jti2) nor the
        # immediately-previous one (jti1), so it's outside the grace window.
        assert client.post(REFRESH_URL, headers=csrf_header(client)).status_code == 200
        current_csrf = csrf_header(client)
        assert client.post(REFRESH_URL, headers=current_csrf).status_code == 200
        current_cookie = client.get_cookie("refresh_token_cookie").value
        current_csrf = csrf_header(client)

        # Replay the original (now doubly-stale) token.
        client.set_cookie("refresh_token_cookie", jti0_cookie)
        replay_resp = client.post(REFRESH_URL, headers=jti0_csrf)
        assert replay_resp.status_code == 401
        assert replay_resp.get_json()["error"]["code"] == "REFRESH_TOKEN_REUSED"

        # The family is now dead — even the legitimately-current token no
        # longer works.
        client.set_cookie("refresh_token_cookie", current_cookie)
        still_dead = client.post(REFRESH_URL, headers=current_csrf)
        assert still_dead.status_code == 401
        assert still_dead.get_json()["error"]["code"] == "REFRESH_SESSION_INVALID"

    def test_grace_window_tolerates_a_benign_concurrent_refresh(self, client):
        """Two legitimate concurrent /refresh calls from the same session
        (e.g. two browser tabs) is a normal race, not theft — replaying the
        *immediately*-previous token (not two-rotations-stale) must still
        succeed, not be flagged as reuse."""
        register(client)
        login(client)
        jti0_cookie = client.get_cookie("refresh_token_cookie").value
        jti0_csrf = csrf_header(client)

        # One legitimate rotation — jti0 becomes the immediately-previous jti.
        assert client.post(REFRESH_URL, headers=csrf_header(client)).status_code == 200

        # A second tab, still holding jti0, refreshes moments later.
        client.set_cookie("refresh_token_cookie", jti0_cookie)
        benign_race_resp = client.post(REFRESH_URL, headers=jti0_csrf)
        assert benign_race_resp.status_code == 200


# ─── Logout ───────────────────────────────────────────────────────────────────


class TestLogout:
    def test_logout_happy_path(self, client):
        register(client)
        login_resp = login(client)
        access_token = login_resp.get_json()["data"]["access_token"]

        resp = client.post(LOGOUT_URL, headers=auth_header(access_token))
        assert resp.status_code == 200
        # Refresh cookie should be cleared (Max-Age=0 or Expires in the past).
        set_cookie_headers = resp.headers.getlist("Set-Cookie")
        refresh_cleared = any(
            "refresh_token" in c and ("Max-Age=0" in c or "expires" in c.lower())
            for c in set_cookie_headers
        )
        assert refresh_cleared

    def test_logout_without_access_token(self, client):
        resp = client.post(LOGOUT_URL)
        assert resp.status_code == 401

    def test_logout_kills_the_refresh_family(self, client):
        """ADR-030 — logout revokes the session server-side, not just the
        client-side cookie: a refresh token *captured before logout* (e.g.
        by an attacker, or simply retried after the cookie itself has been
        cleared) must not still work."""
        register(client)
        login_resp = login(client)
        access_token = login_resp.get_json()["data"]["access_token"]
        # Captured before logout — unset_jwt_cookies() clears the client's
        # own cookie jar, so this simulates a copy taken before that happens.
        refresh_cookie = client.get_cookie("refresh_token_cookie").value
        refresh_csrf = csrf_header(client)

        resp = client.post(LOGOUT_URL, headers=auth_header(access_token))
        assert resp.status_code == 200

        # Restore the pre-logout refresh token and confirm the family is dead.
        client.set_cookie("refresh_token_cookie", refresh_cookie)
        refresh_resp = client.post(REFRESH_URL, headers=refresh_csrf)
        assert refresh_resp.status_code == 401
        assert refresh_resp.get_json()["error"]["code"] == "REFRESH_SESSION_INVALID"
