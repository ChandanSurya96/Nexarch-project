"""Rules-based strategy auto-categorization for verified portfolios (Milestone 7).

Of the 8 fixed categories in app/data/strategy_categories.py, only 3 are
honestly computable from data this codebase currently ingests: Small-cap
Specialist (market-cap allocation), Low-risk (volatility, ADR-024), and
Momentum (trailing price return, ADR-028) — reusing analytics_service's
existing computations, no new data source. Growth, Value, Dividend, and ETF
would need fundamentals/valuation/dividend/instrument-type data nothing in
this codebase ingests yet; Long-term has no validated stability threshold
without real production sync history to calibrate against. All five are
deliberately deferred — see ADR-028 in docs/decisions.md — rather than
guessed at with a shaky heuristic. Public Investor Library portfolios are
untouched by this module entirely: their tags stay human-curated via
scripts/seed_public_investors.py.

COMPLIANCE — every explanation string here must stay strictly descriptive
of what the data currently shows, never a recommendation or a promise (see
docs/security.md "The Line Between Data and Advice": "Discovery filters by
strategy... are fine as descriptive labels of what a portfolio already
does; they become risky the moment UI copy implies 'invest like this.'").
No composite confidence score either (ADR-007) — each explanation cites
the actual observed number against its threshold, the same "labeled,
independently-understandable indicator" style as Portfolio Health.
"""

from __future__ import annotations

from app.data.strategy_categories import STRATEGY_CATEGORIES
from app.extensions import db
from app.models.holding import Holding
from app.models.strategy_category import StrategyCategory
from app.services.analytics_service import compute_market_cap_allocation

# Strictly greater than — same tie-breaking convention strategy_overview_service
# already uses (an exact 50/50 split has no dominant category either).
_SMALL_CAP_MAJORITY_THRESHOLD = 0.5

# Annualized, <=. Roughly Nifty 50's own long-run annualized volatility band —
# a portfolio at or below this is at-or-below broad-market equity risk, given
# this product only models equities.
_LOW_RISK_VOLATILITY_THRESHOLD = 0.15

# >=, trailing ~90 calendar days (see analytics_service's momentum lookback).
_MOMENTUM_RETURN_THRESHOLD = 0.10

_NAME_BY_SLUG = {entry["slug"]: entry["name"] for entry in STRATEGY_CATEGORIES}


def _evaluate_small_cap_specialist(holdings: list[Holding]) -> dict | None:
    allocation = compute_market_cap_allocation(holdings)
    small_fraction = allocation.get("small", 0.0)
    if small_fraction <= _SMALL_CAP_MAJORITY_THRESHOLD:
        return None
    return {
        "slug": "small-cap-specialist",
        "name": _NAME_BY_SLUG["small-cap-specialist"],
        "explanation": (
            f"{round(small_fraction * 100)}% of portfolio value is in small-cap holdings "
            f"(threshold: {round(_SMALL_CAP_MAJORITY_THRESHOLD * 100)}%)."
        ),
    }


def _evaluate_low_risk(health_metrics: dict) -> dict | None:
    volatility = health_metrics.get("volatility")
    if volatility is None or volatility > _LOW_RISK_VOLATILITY_THRESHOLD:
        return None
    return {
        "slug": "low-risk",
        "name": _NAME_BY_SLUG["low-risk"],
        "explanation": (
            f"Annualized volatility of {round(volatility * 100, 1)}% is at or below the "
            f"{round(_LOW_RISK_VOLATILITY_THRESHOLD * 100)}% threshold for lower-than-typical "
            "broad-market equity risk."
        ),
    }


def _evaluate_momentum(health_metrics: dict) -> dict | None:
    momentum = health_metrics.get("momentum")
    if momentum is None or momentum < _MOMENTUM_RETURN_THRESHOLD:
        return None
    return {
        "slug": "momentum",
        "name": _NAME_BY_SLUG["momentum"],
        "explanation": (
            f"Portfolio value is up {round(momentum * 100, 1)}% over the trailing ~90 days "
            f"(threshold: {round(_MOMENTUM_RETURN_THRESHOLD * 100)}%)."
        ),
    }


def categorize(holdings: list[Holding], health_metrics: dict) -> list[dict]:
    """Which of the 3 auto-computable categories currently apply, each with
    a plain-language explanation citing the observed number. Pure — no DB
    access — so the exact same function decides which PortfolioStrategyTag
    rows sync_service writes and which explanations get shown on read; the
    two can never drift apart from each other."""
    evaluations = [
        _evaluate_small_cap_specialist(holdings),
        _evaluate_low_risk(health_metrics),
        _evaluate_momentum(health_metrics),
    ]
    return [match for match in evaluations if match is not None]


def ensure_strategy_category_rows() -> dict[str, StrategyCategory]:
    """Create any of the 8 canonical StrategyCategory rows that don't exist
    yet, return {slug: StrategyCategory} for all of them.

    Runtime, not a migration: tests build the schema via create_all()
    (tests/conftest.py), not Alembic, so seeding via a migration would never
    run there. Cheap (one indexed slug IN (...) query) and idempotent —
    called every sync, same "recompute every time" pattern already used for
    Holding rows in sync_service.run_sync.
    """
    slugs = [entry["slug"] for entry in STRATEGY_CATEGORIES]
    existing = {
        category.slug: category
        for category in StrategyCategory.query.filter(StrategyCategory.slug.in_(slugs)).all()
    }

    for entry in STRATEGY_CATEGORIES:
        if entry["slug"] in existing:
            continue
        category = StrategyCategory(**entry)
        db.session.add(category)
        existing[entry["slug"]] = category

    db.session.flush()
    return existing
