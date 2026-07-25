"""Auth blueprint.

Endpoints (all under /api/v1/auth — prefix registered in create_app):
    POST /register     — create account
    POST /login        — exchange credentials for tokens
    POST /refresh      — get a new access token (reads refresh cookie)
    POST /logout       — clear refresh cookie

Token model (ADR-004, api.md):
    - Access token: short-lived (15 min), returned in the JSON response body.
    - Refresh token: long-lived (30 days), set/cleared as an httpOnly cookie —
      never in the response body or JS-accessible storage.
"""

from flask import Blueprint, request
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    get_jwt_identity,
    jwt_required,
    set_refresh_cookies,
    unset_jwt_cookies,
)
from marshmallow import ValidationError

from app.schemas.auth import LoginSchema, RegisterSchema
from app.services import audit_service
from app.services.auth_service import AuthError, authenticate_user, register_user
from app.utils.responses import error, success

auth_bp = Blueprint("auth", __name__)

_register_schema = RegisterSchema()
_login_schema = LoginSchema()


@auth_bp.post("/register")
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
    access_token = create_access_token(identity=identity)
    refresh_token = create_refresh_token(identity=identity)

    response, status_code = success({"access_token": access_token})
    # Set the refresh token as an httpOnly cookie — not in the body.
    set_refresh_cookies(response, refresh_token)
    return response, status_code


@auth_bp.post("/refresh")
@jwt_required(refresh=True)  # reads from the httpOnly refresh cookie
def refresh():
    """POST /api/v1/auth/refresh

    Reads the refresh token from the httpOnly cookie.
    Returns a new access token in the body and rotates the refresh cookie.
    Returns 401 if the refresh token is missing or invalid.
    """
    identity = get_jwt_identity()
    new_access_token = create_access_token(identity=identity)
    new_refresh_token = create_refresh_token(identity=identity)
    audit_service.log_event(identity, "token_refresh")

    response, status_code = success({"access_token": new_access_token})
    set_refresh_cookies(response, new_refresh_token)
    return response, status_code


@auth_bp.post("/logout")
@jwt_required()
def logout():
    """POST /api/v1/auth/logout — requires a valid access token.

    Clears the refresh cookie. The access token is not invalidated server-side
    (token blacklisting is a Milestone 2+ concern — see task.md).
    Returns 200 with data: null.
    """
    response, status_code = success(None)
    unset_jwt_cookies(response)
    return response, status_code
