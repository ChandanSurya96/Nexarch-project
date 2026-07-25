"""Tests for app/services/analytics_service.py.

HHI/diversification math checked against docs/product-requirements.md's own
example: "A single-sector portfolio scores 1.0 (maximally concentrated)."
"""

from datetime import date

from app.models.holding import Holding
from app.models.portfolio_snapshot import PortfolioSnapshot
from app.services.analytics_service import (
    compute_asset_allocation,
    compute_diversification_score,
    compute_health_metrics,
    compute_hhi,
    compute_portfolio_age_days,
    compute_sector_allocation,
    compute_total_value,
)


def _holding(sector: str, quantity: float, avg_cost_price: float) -> Holding:
    return Holding(
        symbol="TEST",
        sector=sector,
        quantity=quantity,
        avg_cost_price=avg_cost_price,
        as_of_date=date(2026, 7, 25),
    )


class TestSectorAllocation:
    def test_single_sector_is_full_weight(self):
        holdings = [_holding("Financials", 10, 100), _holding("Financials", 5, 200)]
        allocation = compute_sector_allocation(holdings)
        assert allocation == {"Financials": 1.0}

    def test_two_sectors_split_by_value(self):
        # 1000 in Financials, 1000 in IT -> 50/50
        holdings = [_holding("Financials", 10, 100), _holding("IT", 20, 50)]
        allocation = compute_sector_allocation(holdings)
        assert allocation == {"Financials": 0.5, "IT": 0.5}

    def test_no_holdings_returns_empty(self):
        assert compute_sector_allocation([]) == {}

    def test_missing_sector_groups_as_other(self):
        holdings = [_holding(None, 10, 100)]
        allocation = compute_sector_allocation(holdings)
        assert allocation == {"Other": 1.0}


class TestHHI:
    def test_single_sector_scores_one(self):
        # Per docs/product-requirements.md: single-sector = maximally concentrated = 1.0
        assert compute_hhi({"Financials": 1.0}) == 1.0

    def test_four_even_sectors(self):
        allocation = {"A": 0.25, "B": 0.25, "C": 0.25, "D": 0.25}
        assert compute_hhi(allocation) == 0.25

    def test_empty_allocation_scores_zero(self):
        assert compute_hhi({}) == 0.0


class TestDiversificationScore:
    def test_inverse_of_hhi(self):
        assert compute_diversification_score(1.0) == 0.0
        assert compute_diversification_score(0.25) == 0.75
        assert compute_diversification_score(0.0) == 1.0


class TestTotalValue:
    def test_sums_quantity_times_avg_cost(self):
        holdings = [_holding("A", 10, 100), _holding("B", 5, 200)]
        assert compute_total_value(holdings) == 2000.0

    def test_none_avg_cost_treated_as_zero(self):
        holding = Holding(
            symbol="X", quantity=10, avg_cost_price=None, as_of_date=date(2026, 7, 25)
        )
        assert compute_total_value([holding]) == 0.0


class TestAssetAllocation:
    def test_empty_holdings(self):
        assert compute_asset_allocation([]) == {}

    def test_nonempty_is_all_equity(self):
        # See module docstring: only equities are ingested in this milestone.
        holdings = [_holding("Financials", 10, 100)]
        assert compute_asset_allocation(holdings) == {"Equity": 1.0}


class TestPortfolioAgeDays:
    def test_no_snapshots_is_zero(self):
        assert compute_portfolio_age_days([]) == 0

    def test_age_from_earliest_snapshot(self):
        thirty_days_ago = date.today().replace(day=1)
        snapshot = PortfolioSnapshot(snapshot_date=thirty_days_ago)
        age = compute_portfolio_age_days([snapshot])
        assert age == (date.today() - thirty_days_ago).days


class TestHealthMetrics:
    def test_no_composite_score_field(self):
        # ADR-007: no single trust score anywhere in this dict.
        holdings = [_holding("Financials", 10, 100)]
        health = compute_health_metrics(holdings, [])
        assert "score" not in health
        assert "trust_score" not in health

    def test_no_volatility_field(self):
        # ADR-008: absence, not a null placeholder.
        holdings = [_holding("Financials", 10, 100)]
        health = compute_health_metrics(holdings, [])
        assert "volatility" not in health
        assert "risk" not in health

    def test_expected_keys_present(self):
        holdings = [_holding("Financials", 10, 100)]
        health = compute_health_metrics(holdings, [])
        assert set(health.keys()) == {
            "diversification_score",
            "sector_concentration_hhi",
            "portfolio_age_days",
            "holding_count",
        }
        assert health["holding_count"] == 1
