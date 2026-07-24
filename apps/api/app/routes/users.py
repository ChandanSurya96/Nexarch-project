"""Users blueprint.

Endpoints (all under /api/v1/users — prefix registered in create_app):
    GET  /me         — return the authenticated user's profile
    PATCH /me        — update profile (Milestone 2+, stub only)
    GET  /:username  — public profile (Milestone 2+, stub only)

Only GET /me is implemented in Milestone 1 — it serves as the JWT
verification step (replacing the dummy protected endpoint removed from scope).
"""

import uuid

from flask import Blueprint
from flask_jwt_extended import get_jwt_identity, jwt_required

from app.extensions import db
from app.models.user import User
from app.schemas.user import UserSchema
from app.utils.responses import error, success

users_bp = Blueprint("users", __name__)

_user_schema = UserSchema()


@users_bp.get("/me")
@jwt_required()
def get_me():
    """GET /api/v1/users/me

    Returns the authenticated user's profile.
    Requires a valid Bearer access token.
    Returns 401 if the token is missing or invalid (handled by flask-jwt-extended).
    Returns 404 if the user ID in the token no longer exists (shouldn't happen
    in normal operation but handles the edge case cleanly).
    """
    user_id = uuid.UUID(get_jwt_identity())
    user = db.session.get(User, user_id)

    if user is None:
        return error("USER_NOT_FOUND", "User not found.", 404)

    return success(_user_schema.dump(user))
