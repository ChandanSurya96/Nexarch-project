"""Portfolios blueprint.

Endpoints (all under /api/v1/portfolios — prefix registered in create_app):
    GET    /:id             — portfolio detail (public portfolios need no auth)
    GET    /:id/holdings    — current holdings
    GET    /:id/analytics   — allocation + health metrics + strategy overview
    GET    /:id/activity    — descriptive snapshot-history diffs (ADR-015)
    GET    /:id/history     — raw snapshot history over time (Milestone 5)
    GET    /:id/profile     — detail + holdings + analytics + activity combined
    GET    /compare         — side-by-side comparison of two portfolios + diff (Milestone 6)
    PATCH  /:id             — toggle is_public (owner only)
    POST   /:id/follow      — follow (no capital, no execution — see docs/product-requirements.md)
    DELETE /:id/follow      — unfollow

See docs/api.md "Portfolios & Holdings" and "Follows". The GET routes use
optional JWT so a public portfolio is viewable by anyone (per
docs/product/user-journey.md — browsing shouldn't require an account), while
still resolving the caller's identity when present so an owner can view
their own private portfolio.

Routes are thin wrappers around app/services/portfolio_profile_service.py,
which coordinates the specialized services (analytics, activity, strategy
overview) — none of which know this coordinator exists. See that module's
docstring for the layering rationale.
"""

import uuid

from flask import Blueprint, request
from flask_jwt_extended import get_jwt_identity, jwt_required
from marshmallow import ValidationError

from app.schemas.pagination import OptionalPaginationQuerySchema
from app.schemas.portfolio import CompareQuerySchema, PortfolioSchema, PortfolioUpdateSchema
from app.services import portfolio_comparison_service, portfolio_profile_service
from app.services.follow_service import follow, unfollow
from app.services.portfolio_service import PortfolioAccessError, update_visibility
from app.utils.responses import error, format_validation_error, success

portfolios_bp = Blueprint("portfolios", __name__)

_portfolio_schema = PortfolioSchema()
_update_schema = PortfolioUpdateSchema()
_compare_query_schema = CompareQuerySchema()
_optional_pagination_schema = OptionalPaginationQuerySchema()


def _current_user_id() -> uuid.UUID | None:
    identity = get_jwt_identity()
    return uuid.UUID(identity) if identity else None


@portfolios_bp.get("/<uuid:portfolio_id>")
@jwt_required(optional=True)
def get_portfolio(portfolio_id: uuid.UUID):
    try:
        return success(portfolio_profile_service.get_detail(portfolio_id, _current_user_id()))
    except PortfolioAccessError as exc:
        return error(exc.code, exc.message, exc.status)


@portfolios_bp.get("/<uuid:portfolio_id>/holdings")
@jwt_required(optional=True)
def get_holdings(portfolio_id: uuid.UUID):
    try:
        return success(
            portfolio_profile_service.get_holdings_view(portfolio_id, _current_user_id())
        )
    except PortfolioAccessError as exc:
        return error(exc.code, exc.message, exc.status)


@portfolios_bp.get("/<uuid:portfolio_id>/analytics")
@jwt_required(optional=True)
def get_analytics(portfolio_id: uuid.UUID):
    try:
        return success(
            portfolio_profile_service.get_analytics_view(portfolio_id, _current_user_id())
        )
    except PortfolioAccessError as exc:
        return error(exc.code, exc.message, exc.status)


@portfolios_bp.get("/<uuid:portfolio_id>/activity")
@jwt_required(optional=True)
def get_portfolio_activity(portfolio_id: uuid.UUID):
    try:
        params = _optional_pagination_schema.load(request.args.to_dict())
    except ValidationError as exc:
        return error("VALIDATION_ERROR", format_validation_error(exc.messages), 400)

    try:
        entries, pagination = portfolio_profile_service.get_activity_view(
            portfolio_id, _current_user_id(), params["page"], params["per_page"]
        )
    except PortfolioAccessError as exc:
        return error(exc.code, exc.message, exc.status)

    # meta stays empty unless pagination was explicitly requested (ADR-038),
    # so the default response shape is unchanged for existing clients.
    return success(entries, meta={"pagination": pagination} if pagination else None)


@portfolios_bp.get("/<uuid:portfolio_id>/history")
@jwt_required(optional=True)
def get_portfolio_history(portfolio_id: uuid.UUID):
    try:
        params = _optional_pagination_schema.load(request.args.to_dict())
    except ValidationError as exc:
        return error("VALIDATION_ERROR", format_validation_error(exc.messages), 400)

    try:
        entries, pagination = portfolio_profile_service.get_history_view(
            portfolio_id, _current_user_id(), params["page"], params["per_page"]
        )
    except PortfolioAccessError as exc:
        return error(exc.code, exc.message, exc.status)

    return success(entries, meta={"pagination": pagination} if pagination else None)


@portfolios_bp.get("/<uuid:portfolio_id>/profile")
@jwt_required(optional=True)
def get_portfolio_profile(portfolio_id: uuid.UUID):
    try:
        return success(
            portfolio_profile_service.get_complete_profile(portfolio_id, _current_user_id())
        )
    except PortfolioAccessError as exc:
        return error(exc.code, exc.message, exc.status)


@portfolios_bp.get("/compare")
@jwt_required(optional=True)
def compare_portfolios():
    try:
        params = _compare_query_schema.load(request.args.to_dict())
    except ValidationError as exc:
        return error("VALIDATION_ERROR", format_validation_error(exc.messages), 400)

    try:
        return success(portfolio_comparison_service.compare(params["ids"], _current_user_id()))
    except PortfolioAccessError as exc:
        return error(exc.code, exc.message, exc.status)


@portfolios_bp.patch("/<uuid:portfolio_id>")
@jwt_required()
def patch_portfolio(portfolio_id: uuid.UUID):
    try:
        data = _update_schema.load(request.get_json(silent=True) or {})
    except ValidationError as exc:
        return error("VALIDATION_ERROR", format_validation_error(exc.messages), 400)

    user_id = uuid.UUID(get_jwt_identity())
    try:
        portfolio = update_visibility(user_id, portfolio_id, data["is_public"])
    except PortfolioAccessError as exc:
        return error(exc.code, exc.message, exc.status)

    return success(_portfolio_schema.dump(portfolio))


@portfolios_bp.post("/<uuid:portfolio_id>/follow")
@jwt_required()
def follow_portfolio(portfolio_id: uuid.UUID):
    user_id = uuid.UUID(get_jwt_identity())
    try:
        follow(user_id, portfolio_id)
    except PortfolioAccessError as exc:
        return error(exc.code, exc.message, exc.status)

    return success({"followed": True}, status=201)


@portfolios_bp.delete("/<uuid:portfolio_id>/follow")
@jwt_required()
def unfollow_portfolio(portfolio_id: uuid.UUID):
    user_id = uuid.UUID(get_jwt_identity())
    unfollow(user_id, portfolio_id)
    return success({"followed": False})
