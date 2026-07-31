"""Auth blueprint.

Endpoints (all under /api/v1/auth — prefix registered in create_app):
    POST /register     — create account
    POST /login        — exchange credentials for tokens
    POST /refresh      — get a new access token (reads refresh cookie)
    POST /logout       — clear refresh cookie, revoke the session server-side

Token model (ADR-004, api.md):
    - Access token: short-lived (15 min), returned in the JSON response body.
    - Refresh token: long-lived (30 days), set/cleared as an httpOnly cookie —
      never in the response body or JS-accessible storage.

Refresh-token rotation with reuse detection (ADR-030): both tokens carry a
`fid` (family id) custom claim. login/refresh/logout all go through
refresh_token_service.py, which is the only place that reads/writes the
Redis-backed family state — see that module's docstring for the full
reuse-detection design.
"""

from flask import Blueprint, request
from flask_jwt_extended import (
    get_jwt,
    get_jwt_identity,
    jwt_required,
    set_refresh_cookies,
    unset_jwt_cookies,
)
from marshmallow import ValidationError

from app.extensions import limiter
from app.schemas.auth import LoginSchema, RegisterSchema
from app.services import audit_service, refresh_token_service
from app.services.auth_service import AuthError, authenticate_user, register_user
from app.services.refresh_token_service import RefreshReuseError, RefreshSessionInvalidError
from app.utils.responses import error, success

auth_bp = Blueprint("auth", __name__)

_register_schema = RegisterSchema()
_login_schema = LoginSchema()


@auth_bp.post("/register")
@limiter.limit("10 per hour")
def register():
    """POST /api/v1/auth/register — { email, password, username }

    Returns 201 with { user_id, email, username } on success.
    Returns 400 on validation errors, 409 if email or username already taken.
    """
    try:
        data = _register_schema.load(request.get_json(silent=True) or {})
    except ValidationError as exc:
        return error("VALIDATION_ERROR", str(exc.messages), 400)

    try:
        user = register_user(
            email=data["email"],
            password=data["password"],
            username=data["username"],
        )
    except AuthError as exc:
        return error(exc.code, exc.message, exc.status)

    return success(
        {"user_id": str(user.id), "email": user.email, "username": user.username},
        status=201,
    )


@auth_bp.post("/login")
@limiter.limit("5 per minute;20 per hour")
def login():
    """POST /api/v1/auth/login — { email, password }

    Returns 200 with { access_token } in the body.
    Sets the refresh_token as an httpOnly cookie (never in the body).
    Returns 400 on validation errors, 401 on invalid credentials.
    """
    try:
        data = _login_schema.load(request.get_json(silent=True) or {})
    except ValidationError as exc:
        return error("VALIDATION_ERROR", str(exc.messages), 400)

    try:
        user = authenticate_user(email=data["email"], password=data["password"])
    except AuthError as exc:
        return error(exc.code, exc.message, exc.status)

    identity = str(user.id)
    access_token, refresh_token = refresh_token_service.issue_new_family(identity)
    # No audit call here on purpose — authenticate_user() already logged the
    # "login" event. Logging it again here (as this route did) wrote two rows
    # per successful login.

    response, status_code = success({"access_token": access_token})
    # Set the refresh token as an httpOnly cookie — not in the body.
    set_refresh_cookies(response, refresh_token)
    return response, status_code


@auth_bp.post("/refresh")
@jwt_required(refresh=True)  # reads from the httpOnly refresh cookie
def refresh():
    """POST /api/v1/auth/refresh

    Reads the refresh token from the httpOnly cookie, rotates it (ADR-030).
    Returns a new access token in the body and a new refresh cookie.
    Returns 401 if the refresh token is missing, expired, or already used —
    a reused token revokes the whole session family, not just this request.
    """
    identity = get_jwt_identity()
    claims = get_jwt()
    family_id = claims.get("fid")
    incoming_jti = claims["jti"]

    if not family_id:
        # A refresh token issued before ADR-030 (no fid claim) — treat as an
        # invalid session rather than crashing; forces a normal re-login.
        return error("REFRESH_SESSION_INVALID", "Please log in again.", 401)

    try:
        new_access_token, new_refresh_token = refresh_token_service.rotate(
            identity, family_id, incoming_jti
        )
    except RefreshReuseError as exc:
        audit_service.log_event(identity, "refresh_reuse_detected")
        return error("REFRESH_TOKEN_REUSED", str(exc), 401)
    except RefreshSessionInvalidError as exc:
        return error("REFRESH_SESSION_INVALID", str(exc), 401)

    audit_service.log_event(identity, "token_refresh")

    response, status_code = success({"access_token": new_access_token})
    set_refresh_cookies(response, new_refresh_token)
    return response, status_code


@auth_bp.post("/logout")
@jwt_required()
def logout():
    """POST /api/v1/auth/logout — requires a valid access token.

    Clears the refresh cookie AND revokes the session's refresh-token family
    server-side (ADR-030) — a stolen-but-unused refresh token from this
    session becomes immediately dead too, not just the cookie cleared client-side.
    Returns 200 with data: null.
    """
    identity = get_jwt_identity()
    claims = get_jwt()
    family_id = claims.get("fid")
    if family_id:
        refresh_token_service.kill_family(family_id)
    audit_service.log_event(identity, "logout")

    response, status_code = success(None)
    unset_jwt_cookies(response)
    return response, status_code
