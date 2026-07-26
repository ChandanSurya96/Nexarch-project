"""Tests for app/services/strategy_categorization_service.py.

Boundary tests per rule (just below/at/above threshold), categorize()
aggregation, and ensure_strategy_category_rows() idempotency.
"""

from datetime import date

from app.extensions import db
from app.models.holding import Holding
from app.models.strategy_category import StrategyCategory
from app.services.strategy_categorization_service import (
    _evaluate_low_risk,
    _evaluate_momentum,
    _evaluate_small_cap_specialist,
    categorize,
    ensure_strategy_category_rows,
)


def _holding(market_cap_category: str, quantity: float, avg_cost_price: float) -> Holding:
    return Holding(
        symbol="TEST",
        market_cap_category=market_cap_category,
        quantity=quantity,
        avg_cost_price=avg_cost_price,
        as_of_date=date(2026, 7, 25),
    )


class TestEvaluateSmallCapSpecialist:
    def test_majority_small_cap_matches(self):
        holdings = [_holding("small", 10, 100), _holding("large", 5, 100)]  # 2/3 small
        result = _evaluate_small_cap_specialist(holdings)
        assert result is not None
        assert result["slug"] == "small-cap-specialist"
        assert "67%" in result["explanation"]

    def test_exact_tie_does_not_match(self):
        # Exactly 50/50 has no majority — same tie convention as
        # strategy_overview_service._market_cap_phrase.
        holdings = [_holding("small", 10, 100), _holding("large", 10, 100)]
        assert _evaluate_small_cap_specialist(holdings) is None

    def test_minority_small_cap_does_not_match(self):
        holdings = [_holding("small", 3, 100), _holding("large", 7, 100)]
        assert _evaluate_small_cap_specialist(holdings) is None

    def test_no_holdings_does_not_match(self):
        assert _evaluate_small_cap_specialist([]) is None


class TestEvaluateLowRisk:
    def test_at_threshold_matches(self):
        result = _evaluate_low_risk({"volatility": 0.15})
        assert result is not None
        assert result["slug"] == "low-risk"

    def test_below_threshold_matches(self):
        assert _evaluate_low_risk({"volatility": 0.10}) is not None

    def test_above_threshold_does_not_match(self):
        assert _evaluate_low_risk({"volatility": 0.16}) is None

    def test_none_volatility_does_not_match(self):
        assert _evaluate_low_risk({"volatility": None}) is None

    def test_missing_volatility_key_does_not_match(self):
        assert _evaluate_low_risk({}) is None


class TestEvaluateMomentum:
    def test_at_threshold_matches(self):
        result = _evaluate_momentum({"momentum": 0.10})
        assert result is not None
        assert result["slug"] == "momentum"

    def test_above_threshold_matches(self):
        assert _evaluate_momentum({"momentum": 0.15}) is not None

    def test_below_threshold_does_not_match(self):
        assert _evaluate_momentum({"momentum": 0.09}) is None

    def test_negative_momentum_does_not_match(self):
        assert _evaluate_momentum({"momentum": -0.20}) is None

    def test_none_momentum_does_not_match(self):
        assert _evaluate_momentum({"momentum": None}) is None


class TestCategorize:
    def test_matches_multiple_categories_at_once(self):
        holdings = [_holding("small", 10, 100), _holding("large", 2, 100)]  # majority small
        health_metrics = {"volatility": 0.05, "momentum": 0.20}
        results = categorize(holdings, health_metrics)
        slugs = {r["slug"] for r in results}
        assert slugs == {"small-cap-specialist", "low-risk", "momentum"}

    def test_no_matches_returns_empty_list(self):
        holdings = [_holding("large", 10, 100)]
        health_metrics = {"volatility": 0.30, "momentum": -0.05}
        assert categorize(holdings, health_metrics) == []


class TestEnsureStrategyCategoryRows:
    def test_creates_all_eight_when_none_exist(self):
        categories = ensure_strategy_category_rows()
        assert len(categories) == 8
        assert set(categories) == {
            "long-term",
            "growth",
            "value",
            "dividend",
            "momentum",
            "etf",
            "small-cap-specialist",
            "low-risk",
        }

    def test_idempotent_second_call_does_not_duplicate(self):
        ensure_strategy_category_rows()
        db.session.commit()
        ensure_strategy_category_rows()
        db.session.commit()
        assert StrategyCategory.query.count() == 8

    def test_fills_in_missing_subset(self):
        # get-or-create: other tests' committed categories don't roll back
        # between tests (see test_discovery.py's TestStrategyCategories note),
        # so "momentum" may already exist here.
        if StrategyCategory.query.filter_by(slug="momentum").first() is None:
            db.session.add(StrategyCategory(name="Momentum", slug="momentum", description="x"))
            db.session.commit()

        categories = ensure_strategy_category_rows()
        db.session.commit()
        assert len(categories) == 8
        assert StrategyCategory.query.count() == 8
