"""Portfolio read/update business logic — ownership and visibility checks.

See docs/product-requirements.md "Feature: Verified Portfolio Profile" —
private-by-default, and a private portfolio must not be visible to anyone
but its owner (not even leak its existence via a different error code, same
posture as auth_service's unified INVALID_CREDENTIALS — see docs/security.md).
"""

from __future__ import annotations

import uuid

from app.extensions import db
from app.models.portfolio import Portfolio
from app.models.portfolio_snapshot import PortfolioSnapshot


class PortfolioAccessError(Exception):
    def __init__(self, code: str, message: str, status: int) -> None:
        self.code = code
        self.message = message
        self.status = status
        super().__init__(message)


def get_visible_portfolio(
    portfolio_id: uuid.UUID, requesting_user_id: uuid.UUID | None
) -> Portfolio:
    """Return a portfolio if it's public or owned by the requester.

    Raises PORTFOLIO_NOT_FOUND (404) otherwise — deliberately the same error
    for "doesn't exist" and "exists but private," so a private portfolio's
    existence isn't leaked to a non-owner.
    """
    portfolio = db.session.get(Portfolio, portfolio_id)
    is_owner = (
        portfolio is not None
        and requesting_user_id is not None
        and (portfolio.user_id == requesting_user_id)
    )
    if portfolio is None or not (portfolio.is_public or is_owner):
        raise PortfolioAccessError("PORTFOLIO_NOT_FOUND", "Portfolio not found.", 404)
    return portfolio


def update_visibility(user_id: uuid.UUID, portfolio_id: uuid.UUID, is_public: bool) -> Portfolio:
    """Toggle is_public — owner only, per docs/product-requirements.md."""
    portfolio = db.session.get(Portfolio, portfolio_id)
    if portfolio is None or portfolio.user_id != user_id:
        raise PortfolioAccessError("PORTFOLIO_NOT_FOUND", "Portfolio not found.", 404)

    portfolio.is_public = is_public
    db.session.commit()
    return portfolio


def get_latest_snapshot(portfolio_id: uuid.UUID) -> PortfolioSnapshot | None:
    return (
        PortfolioSnapshot.query.filter_by(portfolio_id=portfolio_id)
        .order_by(PortfolioSnapshot.snapshot_date.desc())
        .first()
    )
