"""Portfolio analytics — allocation, concentration, diversification, health.

See docs/product-requirements.md "Portfolio Analytics" / "Portfolio Health"
for the calculation notes and docs/api.md for the response shape this feeds.

KNOWN LIMITATION — "value" here means quantity * avg_cost_price (cost basis),
not live market value. No market-data vendor is selected yet (ADR-008 defers
that to Phase 2), so there's no current-price source to compute true market
value or true volatility. Cost-basis allocation is a reasonable Phase 1 proxy
for "how is this portfolio spread out," but it will drift from true weights
as prices move — this should be called out in the UI, not presented silently
as live value, per the same "don't imply precision that isn't there"
reasoning as ADR-008 itself.

KNOWN LIMITATION — asset_allocation is {"Equity": 1.0} for every portfolio in
this milestone, since Upstox's long-term-holdings endpoint (the only source
wired up so far) only returns equities. This becomes meaningful once a second
instrument type (mutual funds, etc.) is ingested.
"""

from __future__ import annotations

from datetime import date

from app.models.holding import Holding
from app.models.portfolio_snapshot import PortfolioSnapshot


def _holding_value(holding: Holding) -> float:
    if holding.avg_cost_price is None:
        return 0.0
    return float(holding.quantity) * float(holding.avg_cost_price)


def compute_total_value(holdings: list[Holding]) -> float:
    """Sum of quantity * avg_cost_price across all holdings — see the
    cost-basis-vs-market-value limitation in the module docstring."""
    return round(sum(_holding_value(h) for h in holdings), 6)


def compute_sector_allocation(holdings: list[Holding]) -> dict[str, float]:
    """Sector -> fraction of total value (0..1). Unmapped sector groups as "Other"."""
    total = sum(_holding_value(h) for h in holdings)
    if total <= 0:
        return {}

    totals_by_sector: dict[str, float] = {}
    for holding in holdings:
        sector = holding.sector or "Other"
        totals_by_sector[sector] = totals_by_sector.get(sector, 0.0) + _holding_value(holding)

    return {sector: round(value / total, 4) for sector, value in totals_by_sector.items()}


def compute_market_cap_allocation(holdings: list[Holding]) -> dict[str, float]:
    """Market-cap category -> fraction of total value (0..1). Unmapped
    categories group as "Other" (see the sector_mapping limitation, ADR-013)."""
    total = sum(_holding_value(h) for h in holdings)
    if total <= 0:
        return {}

    totals_by_category: dict[str, float] = {}
    for holding in holdings:
        category = holding.market_cap_category or "Other"
        totals_by_category[category] = totals_by_category.get(category, 0.0) + _holding_value(
            holding
        )

    return {category: round(value / total, 4) for category, value in totals_by_category.items()}


def compute_asset_allocation(holdings: list[Holding]) -> dict[str, float]:
    """See module docstring — every holding synced so far is equity."""
    if not holdings:
        return {}
    return {"Equity": 1.0}


def compute_hhi(sector_allocation: dict[str, float]) -> float:
    """Herfindahl-Hirschman Index of sector weights — sum of squared fractions.

    1.0 = single-sector (maximally concentrated), approaches 0 = evenly spread
    across many sectors. See docs/product-requirements.md.
    """
    return round(sum(weight**2 for weight in sector_allocation.values()), 4)


def compute_diversification_score(hhi: float) -> float:
    """Inverse of concentration: 1 - HHI. See module note in docs/api.md's
    example — the two fields aren't independently defined there, so this is
    the derivation this codebase uses."""
    return round(1 - hhi, 4)


def compute_portfolio_age_days(snapshots: list[PortfolioSnapshot]) -> int:
    """Days since the earliest snapshot for this portfolio.

    This is time-since-Nexarch-started-tracking, NOT true holding-acquisition
    date — broker holdings endpoints don't reliably expose purchase dates (see
    the design note in docs/decisions.md added alongside ADR-013/ADR-014).
    Returns 0 if there's no snapshot yet (first sync in progress).
    """
    if not snapshots:
        return 0
    earliest = min(s.snapshot_date for s in snapshots)
    return (date.today() - earliest).days


def compute_health_metrics(holdings: list[Holding], snapshots: list[PortfolioSnapshot]) -> dict:
    """Assemble the full health-metrics dict stored on portfolio_snapshots
    and returned by GET /portfolios/:id/analytics (see docs/api.md).

    Deliberately no single composite score (ADR-007) and no volatility/risk
    field (ADR-008) — see docs/product-requirements.md "Portfolio Health".
    """
    sector_allocation = compute_sector_allocation(holdings)
    hhi = compute_hhi(sector_allocation)
    return {
        "diversification_score": compute_diversification_score(hhi),
        "sector_concentration_hhi": hhi,
        "portfolio_age_days": compute_portfolio_age_days(snapshots),
        "holding_count": len(holdings),
    }
