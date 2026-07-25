"""Portfolios blueprint.

Endpoints (all under /api/v1/portfolios — prefix registered in create_app):
    GET   /:id             — portfolio detail (public portfolios need no auth)
    GET   /:id/holdings    — current holdings
    GET   /:id/analytics   — allocation + health metrics
    PATCH /:id             — toggle is_public (owner only)

See docs/api.md "Portfolios & Holdings". The three GET routes use optional
JWT so a public portfolio is viewable by anyone (per docs/product/user-journey.md
— browsing shouldn't require an account), while still resolving the caller's
identity when present so an owner can view their own private portfolio.
"""

import uuid

from flask import Blueprint, request
from flask_jwt_extended import get_jwt_identity, jwt_required
from marshmallow import ValidationError

from app.schemas.portfolio import HoldingSchema, PortfolioSchema, PortfolioUpdateSchema
from app.services.portfolio_service import (
    PortfolioAccessError,
    get_latest_snapshot,
    get_visible_portfolio,
    update_visibility,
)
from app.utils.responses import error, success

portfolios_bp = Blueprint("portfolios", __name__)

_portfolio_schema = PortfolioSchema()
_holding_schema = HoldingSchema()
_update_schema = PortfolioUpdateSchema()


def _current_user_id() -> uuid.UUID | None:
    identity = get_jwt_identity()
    return uuid.UUID(identity) if identity else None


@portfolios_bp.get("/<uuid:portfolio_id>")
@jwt_required(optional=True)
def get_portfolio(portfolio_id: uuid.UUID):
    try:
        portfolio = get_visible_portfolio(portfolio_id, _current_user_id())
    except PortfolioAccessError as exc:
        return error(exc.code, exc.message, exc.status)

    return success(_portfolio_schema.dump(portfolio))


@portfolios_bp.get("/<uuid:portfolio_id>/holdings")
@jwt_required(optional=True)
def get_holdings(portfolio_id: uuid.UUID):
    try:
        portfolio = get_visible_portfolio(portfolio_id, _current_user_id())
    except PortfolioAccessError as exc:
        return error(exc.code, exc.message, exc.status)

    return success(_holding_schema.dump(portfolio.holdings, many=True))


@portfolios_bp.get("/<uuid:portfolio_id>/analytics")
@jwt_required(optional=True)
def get_analytics(portfolio_id: uuid.UUID):
    try:
        get_visible_portfolio(portfolio_id, _current_user_id())  # raises if not visible
    except PortfolioAccessError as exc:
        return error(exc.code, exc.message, exc.status)

    snapshot = get_latest_snapshot(portfolio_id)
    if snapshot is None:
        # No sync has completed yet — honestly empty, not a fabricated shape.
        return success(
            {
                "portfolio_id": str(portfolio_id),
                "total_value": None,
                "sector_allocation": {},
                "health": None,
                "as_of": None,
            }
        )

    return success(
        {
            "portfolio_id": str(portfolio_id),
            "total_value": (
                float(snapshot.total_value) if snapshot.total_value is not None else None
            ),
            "sector_allocation": snapshot.sector_allocation or {},
            "health": snapshot.health_metrics,
            "as_of": snapshot.snapshot_date.isoformat(),
        }
    )


@portfolios_bp.patch("/<uuid:portfolio_id>")
@jwt_required()
def patch_portfolio(portfolio_id: uuid.UUID):
    try:
        data = _update_schema.load(request.get_json(silent=True) or {})
    except ValidationError as exc:
        return error("VALIDATION_ERROR", str(exc.messages), 400)

    user_id = uuid.UUID(get_jwt_identity())
    try:
        portfolio = update_visibility(user_id, portfolio_id, data["is_public"])
    except PortfolioAccessError as exc:
        return error(exc.code, exc.message, exc.status)

    return success(_portfolio_schema.dump(portfolio))
