"""Users blueprint.

Endpoints (all under /api/v1/users — prefix registered in create_app):
    GET  /me            — return the authenticated user's profile
    PATCH /me           — update profile (Milestone 3+, stub only)
    GET  /:username     — public profile (Milestone 3+, stub only)
    GET  /me/following  — portfolios the caller follows (Milestone 3)
    GET  /me/portfolio  — the caller's own portfolio, or null (Milestone 4b, ADR-019)

Only GET /me was implemented in Milestone 1 — it served as the JWT
verification step (replacing the dummy protected endpoint removed from scope).
GET /me/following is added in Milestone 3 alongside the Follows feature.
"""

import uuid

from flask import Blueprint
from flask_jwt_extended import get_jwt_identity, jwt_required

from app.extensions import db
from app.models.user import User
from app.schemas.portfolio import PortfolioSchema
from app.schemas.user import UserSchema
from app.services.follow_service import list_following
from app.services.portfolio_service import get_my_portfolio
from app.utils.responses import error, success

users_bp = Blueprint("users", __name__)

_user_schema = UserSchema()
_portfolio_schema = PortfolioSchema()


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


@users_bp.get("/me/following")
@jwt_required()
def get_following():
    """GET /api/v1/users/me/following — portfolios the caller follows."""
    user_id = uuid.UUID(get_jwt_identity())
    portfolios = list_following(user_id)
    return success(_portfolio_schema.dump(portfolios, many=True))


@users_bp.get("/me/portfolio")
@jwt_required()
def get_my_portfolio_route():
    """GET /api/v1/users/me/portfolio — the caller's own portfolio.

    Returns data: null (200), not a 404, when none exists yet — a Portfolio
    is only created lazily on first successful sync, so "none yet" is a
    normal state for a new signup, not an error (ADR-019).
    """
    user_id = uuid.UUID(get_jwt_identity())
    portfolio = get_my_portfolio(user_id)
    return success(_portfolio_schema.dump(portfolio) if portfolio else None)
