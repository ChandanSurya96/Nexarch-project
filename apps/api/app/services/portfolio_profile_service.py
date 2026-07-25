"""Coordinates the specialized portfolio services into profile views.

Keeps Flask routes thin (see app/routes/portfolios.py): each route makes one
call here instead of orchestrating multiple services inline. This module
fans out to analytics_service, activity_service, strategy_overview_service,
and Portfolio.holdings — none of which import this module or each other, so
each stays independently usable/testable (see docs/architecture.md's
routes -> services -> models layering).
"""

from __future__ import annotations

import uuid

from app.models.portfolio import Portfolio
from app.schemas.portfolio import (
    HoldingSchema,
    PortfolioAnalyticsSchema,
    PortfolioHistoryEntrySchema,
    PortfolioSchema,
)
from app.services.activity_service import get_activity
from app.services.analytics_service import compute_hhi
from app.services.portfolio_service import (
    get_latest_snapshot,
    get_snapshot_history,
    get_visible_portfolio,
)
from app.services.strategy_overview_service import generate_overview

_portfolio_schema = PortfolioSchema()
_holding_schema = HoldingSchema()
_analytics_schema = PortfolioAnalyticsSchema()
_history_entry_schema = PortfolioHistoryEntrySchema()


def _build_analytics_view(portfolio_id: uuid.UUID, portfolio: Portfolio) -> dict:
    """Moved verbatim from the old routes/portfolios.py:get_analytics body.

    Snapshot fetch + HHI fallback + strategy-overview generation + response
    assembly — the exact orchestration that used to live in the Flask route.
    """
    snapshot = get_latest_snapshot(portfolio_id)
    if snapshot is None:
        # No sync has completed yet — honestly empty, not a fabricated shape.
        return {
            "portfolio_id": str(portfolio_id),
            "total_value": None,
            "sector_allocation": {},
            "health": None,
            "strategy_overview": None,
            "as_of": None,
        }

    sector_allocation = snapshot.sector_allocation or {}
    hhi = (snapshot.health_metrics or {}).get(
        "sector_concentration_hhi", compute_hhi(sector_allocation)
    )

    return {
        "portfolio_id": str(portfolio_id),
        "total_value": (float(snapshot.total_value) if snapshot.total_value is not None else None),
        "sector_allocation": sector_allocation,
        "health": snapshot.health_metrics,
        "strategy_overview": generate_overview(sector_allocation, hhi, portfolio.holdings),
        "as_of": snapshot.snapshot_date.isoformat(),
    }


def get_detail(portfolio_id: uuid.UUID, requesting_user_id: uuid.UUID | None) -> dict:
    portfolio = get_visible_portfolio(portfolio_id, requesting_user_id)
    return _portfolio_schema.dump(portfolio)


def get_holdings_view(portfolio_id: uuid.UUID, requesting_user_id: uuid.UUID | None) -> list[dict]:
    portfolio = get_visible_portfolio(portfolio_id, requesting_user_id)
    return _holding_schema.dump(portfolio.holdings, many=True)


def get_analytics_view(portfolio_id: uuid.UUID, requesting_user_id: uuid.UUID | None) -> dict:
    portfolio = get_visible_portfolio(portfolio_id, requesting_user_id)
    return _analytics_schema.dump(_build_analytics_view(portfolio_id, portfolio))


def get_activity_view(portfolio_id: uuid.UUID, requesting_user_id: uuid.UUID | None) -> list[dict]:
    get_visible_portfolio(portfolio_id, requesting_user_id)  # raises if not visible
    return get_activity(portfolio_id)


def get_history_view(portfolio_id: uuid.UUID, requesting_user_id: uuid.UUID | None) -> list[dict]:
    get_visible_portfolio(portfolio_id, requesting_user_id)  # raises if not visible
    snapshots = get_snapshot_history(portfolio_id)
    return _history_entry_schema.dump(snapshots, many=True)


def get_complete_profile(portfolio_id: uuid.UUID, requesting_user_id: uuid.UUID | None) -> dict:
    """Detail + holdings + analytics + activity in one payload.

    New, additive endpoint (GET /portfolios/:id/profile) — the three
    separate endpoints above are unchanged and still the right choice for
    partial-data use cases; this is a convenience for a single profile-page
    fetch, not a replacement.
    """
    portfolio = get_visible_portfolio(portfolio_id, requesting_user_id)
    return {
        "portfolio": _portfolio_schema.dump(portfolio),
        "holdings": _holding_schema.dump(portfolio.holdings, many=True),
        "analytics": _analytics_schema.dump(_build_analytics_view(portfolio_id, portfolio)),
        "activity": get_activity(portfolio_id),
    }
