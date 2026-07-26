"""Portfolio analytics — allocation, concentration, diversification, health.

See docs/product-requirements.md "Portfolio Analytics" / "Portfolio Health"
for the calculation notes and docs/api.md for the response shape this feeds.

KNOWN LIMITATION — "value" here means quantity * avg_cost_price (cost basis),
not live market value. Cost-basis allocation is a reasonable Phase 1 proxy
for "how is this portfolio spread out," but it will drift from true weights
as prices move — this should be called out in the UI, not presented silently
as live value, per the same "don't imply precision that isn't there"
reasoning as ADR-008/ADR-024.

KNOWN LIMITATION — asset_allocation is {"Equity": 1.0} for every portfolio in
this milestone, since Upstox's long-term-holdings endpoint (the only source
wired up so far) only returns equities. This becomes meaningful once a second
instrument type (mutual funds, etc.) is ingested.

Volatility (ADR-024, resolving ADR-008): annualized stddev of daily log
returns, value-weighted across holdings — see compute_volatility and
compute_portfolio_volatility below. `None` wherever there isn't enough
price history to compute it honestly (no broker connection with historical
data, e.g. Public Investor Library portfolios; or too few data points) —
never a fabricated or interpolated number.

compute_scalar_diff/compute_allocation_diff/compute_health_diff (Milestone
6, Portfolio Comparison) are the exception to every other function in this
module: they diff two already-computed domain dicts/values rather than
taking raw ORM input for a single portfolio.
"""

from __future__ import annotations

import math
import uuid
from datetime import date

from app.models.holding import Holding
from app.models.portfolio_snapshot import PortfolioSnapshot

# Fewer data points than this isn't a real signal — an honestly absent
# volatility, not a noisy one.
_MIN_PRICE_POINTS_FOR_VOLATILITY = 20
_TRADING_DAYS_PER_YEAR = 252


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


def compute_volatility(closes: list[float]) -> float | None:
    """Annualized volatility from a series of daily closing prices —
    stddev of daily log returns * sqrt(252 trading days).

    None if there are too few data points (ADR-024) — a short series
    produces a statistically meaningless number that would look precise
    without being one.
    """
    if len(closes) < _MIN_PRICE_POINTS_FOR_VOLATILITY:
        return None

    log_returns = [
        math.log(closes[i] / closes[i - 1])
        for i in range(1, len(closes))
        if closes[i - 1] > 0 and closes[i] > 0
    ]
    if len(log_returns) < _MIN_PRICE_POINTS_FOR_VOLATILITY - 1:
        return None

    mean_return = sum(log_returns) / len(log_returns)
    variance = sum((r - mean_return) ** 2 for r in log_returns) / (len(log_returns) - 1)
    daily_stddev = math.sqrt(variance)
    return round(daily_stddev * math.sqrt(_TRADING_DAYS_PER_YEAR), 4)


def compute_portfolio_volatility(
    holdings: list[Holding], closes_by_holding_id: dict[uuid.UUID, list[float]]
) -> float | None:
    """Value-weighted portfolio volatility — same value-weighting
    compute_sector_allocation already uses.

    Holdings with no usable price history are excluded, not zero-filled:
    the result is renormalized over the weight of holdings that actually
    contributed, so missing data for one holding doesn't silently drag the
    whole figure down. None if no holding contributed at all.
    """
    total = sum(_holding_value(h) for h in holdings)
    if total <= 0:
        return None

    weighted_sum = 0.0
    weighted_total = 0.0
    for holding in holdings:
        closes = closes_by_holding_id.get(holding.id)
        if not closes:
            continue
        volatility = compute_volatility(closes)
        if volatility is None:
            continue
        weight = _holding_value(holding) / total
        weighted_sum += volatility * weight
        weighted_total += weight

    if weighted_total <= 0:
        return None
    return round(weighted_sum / weighted_total, 4)


def compute_health_metrics(
    holdings: list[Holding],
    snapshots: list[PortfolioSnapshot],
    closes_by_holding_id: dict[uuid.UUID, list[float]] | None = None,
) -> dict:
    """Assemble the full health-metrics dict stored on portfolio_snapshots
    and returned by GET /portfolios/:id/analytics (see docs/api.md).

    Deliberately no single composite score (ADR-007) — see
    docs/product-requirements.md "Portfolio Health". `volatility` (ADR-024)
    is `None` whenever `closes_by_holding_id` isn't supplied or doesn't
    yield enough data — the same honest-absence convention as every other
    nullable field in this API, not a fabricated number.
    """
    sector_allocation = compute_sector_allocation(holdings)
    hhi = compute_hhi(sector_allocation)
    return {
        "diversification_score": compute_diversification_score(hhi),
        "sector_concentration_hhi": hhi,
        "portfolio_age_days": compute_portfolio_age_days(snapshots),
        "holding_count": len(holdings),
        "volatility": (
            compute_portfolio_volatility(holdings, closes_by_holding_id)
            if closes_by_holding_id
            else None
        ),
    }


_HEALTH_DIFF_FIELDS = (
    "diversification_score",
    "sector_concentration_hhi",
    "portfolio_age_days",
    "holding_count",
    "volatility",
)


def compute_scalar_diff(a: float | None, b: float | None) -> dict:
    """{"a", "b", "delta"} for a single numeric comparison, `b - a`.

    `delta` is `None` if either side is `None` — diffing against missing
    data would produce a number that looks precise without being one, the
    same convention ADR-024 already established for volatility.
    """
    delta = round(b - a, 6) if a is not None and b is not None else None
    return {"a": a, "b": b, "delta": delta}


def compute_allocation_diff(
    allocation_a: dict[str, float] | None, allocation_b: dict[str, float] | None
) -> dict[str, dict]:
    """Per-sector {"a", "b", "delta"} across the union of both portfolios'
    sectors. A sector absent from one side's *known* allocation is an
    honest `0.0` — a real computed fact, not missing data (unlike
    volatility's nullability).

    A whole side passed as `None` (no snapshot at all for that portfolio,
    as opposed to a snapshot that simply holds 0% of some sector) is
    different: every sector gets `None` for that side, not a fabricated
    0.0 — otherwise an unsynced portfolio would misleadingly read as
    "confirmed to hold nothing in every sector" rather than "unknown."
    """
    sectors = sorted(set(allocation_a or {}) | set(allocation_b or {}))
    return {
        sector: compute_scalar_diff(
            allocation_a.get(sector, 0.0) if allocation_a is not None else None,
            allocation_b.get(sector, 0.0) if allocation_b is not None else None,
        )
        for sector in sectors
    }


def compute_health_diff(health_a: dict | None, health_b: dict | None) -> dict:
    """Per-field {"a", "b", "delta"} across _HEALTH_DIFF_FIELDS.

    Safe against a whole-side `None` (no snapshot yet for that portfolio)
    and against a missing/None individual field (e.g. a pre-ADR-024
    snapshot with no "volatility" key at all) — both produce a `None` a/b/
    delta for that field rather than raising or fabricating a zero.
    """
    health_a = health_a or {}
    health_b = health_b or {}
    return {
        field: compute_scalar_diff(health_a.get(field), health_b.get(field))
        for field in _HEALTH_DIFF_FIELDS
    }
