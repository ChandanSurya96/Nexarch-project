"""Side-by-side comparison of two portfolios (Milestone 6).

Coordinator, same role as portfolio_profile_service.py: fans out to the
already-existing get_detail/get_analytics_view for each portfolio (each of
which already enforces visibility via get_visible_portfolio) and to
analytics_service's diff functions, then assembles a plain dict — no new
access-control path, no new marshmallow schema, matching
get_complete_profile's existing precedent.
"""

from __future__ import annotations

import uuid

from app.services.analytics_service import (
    compute_allocation_diff,
    compute_health_diff,
    compute_scalar_diff,
)
from app.services.portfolio_profile_service import get_analytics_view, get_detail
from app.services.portfolio_service import PortfolioAccessError


def compare(portfolio_ids: list[uuid.UUID], requesting_user_id: uuid.UUID | None) -> dict:
    id_a, id_b = portfolio_ids
    if id_a == id_b:
        raise PortfolioAccessError(
            "CANNOT_COMPARE_SAME_PORTFOLIO",
            "Choose two different portfolios to compare.",
            400,
        )

    detail_a = get_detail(id_a, requesting_user_id)
    detail_b = get_detail(id_b, requesting_user_id)
    analytics_a = get_analytics_view(id_a, requesting_user_id)
    analytics_b = get_analytics_view(id_b, requesting_user_id)

    # sector_allocation is always a dict ({} rather than None) even when
    # there's no snapshot at all — total_value is None precisely in that
    # case (see portfolio_profile_service._build_analytics_view), so it's
    # the signal used here to tell "no snapshot yet" apart from "a real
    # snapshot with 0% in some sector" before diffing allocations.
    sector_allocation_a = (
        analytics_a["sector_allocation"] if analytics_a["total_value"] is not None else None
    )
    sector_allocation_b = (
        analytics_b["sector_allocation"] if analytics_b["total_value"] is not None else None
    )

    return {
        "portfolios": [
            {"portfolio": detail_a, "analytics": analytics_a},
            {"portfolio": detail_b, "analytics": analytics_b},
        ],
        "diff": {
            "total_value": compute_scalar_diff(
                analytics_a["total_value"], analytics_b["total_value"]
            ),
            "sector_allocation": compute_allocation_diff(sector_allocation_a, sector_allocation_b),
            "health": compute_health_diff(analytics_a["health"], analytics_b["health"]),
        },
    }
