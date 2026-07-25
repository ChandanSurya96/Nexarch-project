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


def get_my_portfolio(user_id: uuid.UUID) -> Portfolio | None:
    """The signed-in user's own portfolio, or None.

    None is a normal, expected state (ADR-019) — a Portfolio row is only
    created lazily on first successful sync (see sync_service.run_sync), so
    every new signup, and even a user who just finished a broker connection
    seconds ago, legitimately has no Portfolio yet.
    """
    return Portfolio.query.filter_by(user_id=user_id).first()


def get_latest_snapshot(portfolio_id: uuid.UUID) -> PortfolioSnapshot | None:
    """The most recent snapshot. snapshot_date alone isn't unique per
    portfolio (ADR-025) — more than one sync can land on the same calendar
    date — so created_at is the tiebreaker that makes "latest" deterministic
    rather than whichever same-date row the database happens to return first.
    """
    return (
        PortfolioSnapshot.query.filter_by(portfolio_id=portfolio_id)
        .order_by(PortfolioSnapshot.snapshot_date.desc(), PortfolioSnapshot.created_at.desc())
        .first()
    )


def get_snapshot_history(portfolio_id: uuid.UUID) -> list[PortfolioSnapshot]:
    """Oldest-to-newest snapshot history — powers GET /portfolios/:id/history,
    documented since Phase 0 but not built until Milestone 5. Raw data (every
    snapshot), distinct from the descriptive diffs activity_service produces
    from the same table. created_at as a secondary key (ADR-025) orders
    same-date rows by actual creation time instead of arbitrarily."""
    return (
        PortfolioSnapshot.query.filter_by(portfolio_id=portfolio_id)
        .order_by(PortfolioSnapshot.snapshot_date.asc(), PortfolioSnapshot.created_at.asc())
        .all()
    )


# ── Shared serialization helpers ──────────────────────────────────────────────
# Used by both PortfolioSchema (app/schemas/portfolio.py) and
# discovery_service.py, so the detail view, the following list, and the
# discovery feed describe a portfolio identically wherever they overlap.


def resolve_display_name(portfolio: Portfolio) -> str:
    """'Whose portfolio is this' — the public investor's name, or the
    owning user's display name/username."""
    if portfolio.portfolio_type == "public" and portfolio.public_investor is not None:
        return portfolio.public_investor.name
    if portfolio.user is not None:
        return portfolio.user.display_name or portfolio.user.username
    return "Unknown"


def resolve_strategy_tag_slugs(portfolio: Portfolio) -> list[str]:
    return [tag.strategy_category.slug for tag in portfolio.strategy_tags]


def resolve_latest_health(portfolio: Portfolio) -> dict | None:
    """The most recent snapshot's health_metrics, or None if nothing has
    synced yet — honestly absent, not a fabricated default."""
    if not portfolio.snapshots:
        return None
    latest = max(portfolio.snapshots, key=lambda s: s.snapshot_date)
    return latest.health_metrics
