"""Tests for app/services/analytics_service.py.

HHI/diversification math checked against docs/product-requirements.md's own
example: "A single-sector portfolio scores 1.0 (maximally concentrated)."
"""

import uuid
from datetime import date

import pytest

from app.models.holding import Holding
from app.models.portfolio_snapshot import PortfolioSnapshot
from app.services.analytics_service import (
    compute_allocation_diff,
    compute_asset_allocation,
    compute_diversification_score,
    compute_health_diff,
    compute_health_metrics,
    compute_hhi,
    compute_momentum_return,
    compute_portfolio_age_days,
    compute_portfolio_momentum,
    compute_portfolio_volatility,
    compute_scalar_diff,
    compute_sector_allocation,
    compute_total_value,
    compute_volatility,
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

    def test_volatility_is_none_without_price_data(self):
        # ADR-024 (resolving ADR-008): volatility is now a real field, but
        # honestly None rather than fabricated when there's no price series
        # to compute it from — the same convention as every other nullable
        # field in this API, not a placeholder pretending to be data.
        holdings = [_holding("Financials", 10, 100)]
        health = compute_health_metrics(holdings, [])
        assert health["volatility"] is None
        assert "risk" not in health

    def test_no_composite_risk_score_field(self):
        # ADR-007 still holds: volatility is its own labeled field, not
        # folded into a composite score.
        holdings = [_holding("Financials", 10, 100)]
        health = compute_health_metrics(holdings, [])
        assert "risk_score" not in health

    def test_expected_keys_present(self):
        holdings = [_holding("Financials", 10, 100)]
        health = compute_health_metrics(holdings, [])
        assert set(health.keys()) == {
            "diversification_score",
            "sector_concentration_hhi",
            "portfolio_age_days",
            "holding_count",
            "volatility",
            "momentum",
        }
        assert health["holding_count"] == 1

    def test_momentum_is_none_without_price_data(self):
        # Same honest-absence convention as volatility (ADR-028).
        holdings = [_holding("Financials", 10, 100)]
        health = compute_health_metrics(holdings, [])
        assert health["momentum"] is None


class TestComputeVolatility:
    def test_too_few_points_returns_none(self):
        closes = [100.0 + i for i in range(10)]  # fewer than the 20-point floor
        assert compute_volatility(closes) is None

    def test_constant_price_series_has_zero_volatility(self):
        # No day-to-day change at all -> every log return is 0.
        closes = [100.0] * 25
        assert compute_volatility(closes) == 0.0

    def test_varying_prices_produce_a_positive_number(self):
        closes = [100.0, 102.0, 98.0, 101.0, 97.0] * 5  # 25 points, real variance
        volatility = compute_volatility(closes)
        assert volatility is not None
        assert volatility > 0


class TestComputePortfolioVolatility:
    def _priced_holding(self, quantity: float, avg_cost_price: float) -> Holding:
        return Holding(
            id=uuid.uuid4(),
            symbol="TEST",
            quantity=quantity,
            avg_cost_price=avg_cost_price,
            as_of_date=date(2026, 7, 25),
        )

    def test_none_when_no_holding_has_price_data(self):
        holdings = [self._priced_holding(10, 100)]
        assert compute_portfolio_volatility(holdings, {}) is None

    def test_excludes_holdings_without_price_data_rather_than_zero_filling(self):
        priced = self._priced_holding(10, 100)
        unpriced = self._priced_holding(10, 100)
        varying_closes = [100.0, 102.0, 98.0, 101.0, 97.0] * 5

        result = compute_portfolio_volatility([priced, unpriced], {priced.id: varying_closes})
        solo_volatility = compute_volatility(varying_closes)

        # Only the priced holding contributed — the result should match its
        # own volatility exactly, not be diluted toward zero by the unpriced one.
        assert result == solo_volatility

    def test_value_weighted_average(self):
        # Holding A: value 1000, zero volatility. Holding B: value 1000, some volatility.
        # Equal weight -> result is exactly half of B's own volatility.
        flat_closes = [100.0] * 25
        varying_closes = [100.0, 110.0, 90.0, 105.0, 95.0] * 5

        holding_a = self._priced_holding(quantity=10, avg_cost_price=100)  # value 1000
        holding_b = self._priced_holding(quantity=10, avg_cost_price=100)  # value 1000

        result = compute_portfolio_volatility(
            [holding_a, holding_b],
            {holding_a.id: flat_closes, holding_b.id: varying_closes},
        )
        b_volatility = compute_volatility(varying_closes)
        assert result == round(b_volatility / 2, 4)


class TestMomentum:
    def test_too_few_points_returns_none(self):
        closes = [100.0 + i for i in range(30)]  # fewer than the 64-point floor
        assert compute_momentum_return(closes) is None

    def test_flat_price_series_has_zero_momentum(self):
        closes = [100.0] * 64
        assert compute_momentum_return(closes) == 0.0

    def test_positive_trend(self):
        # 63 trading days back the price was 100, now it's 110 -> +10%.
        closes = [100.0] * 63 + [110.0]
        assert compute_momentum_return(closes) == 0.1

    def test_negative_trend(self):
        closes = [100.0] * 63 + [90.0]
        assert compute_momentum_return(closes) == -0.1

    def test_only_uses_the_trailing_window(self):
        # Extra history further back than the lookback window shouldn't
        # change the result — only the last 64 points matter.
        closes = [50.0] * 100 + [100.0] * 63 + [110.0]
        assert compute_momentum_return(closes) == 0.1


class TestComputePortfolioMomentum:
    def _priced_holding(self, quantity: float, avg_cost_price: float) -> Holding:
        return Holding(
            id=uuid.uuid4(),
            symbol="TEST",
            quantity=quantity,
            avg_cost_price=avg_cost_price,
            as_of_date=date(2026, 7, 25),
        )

    def test_none_when_no_holding_has_price_data(self):
        holdings = [self._priced_holding(10, 100)]
        assert compute_portfolio_momentum(holdings, {}) is None

    def test_excludes_holdings_without_price_data_rather_than_zero_filling(self):
        priced = self._priced_holding(10, 100)
        unpriced = self._priced_holding(10, 100)
        trending_closes = [100.0] * 63 + [110.0]

        result = compute_portfolio_momentum([priced, unpriced], {priced.id: trending_closes})
        solo_momentum = compute_momentum_return(trending_closes)

        assert result == solo_momentum

    def test_value_weighted_average(self):
        flat_closes = [100.0] * 64
        trending_closes = [100.0] * 63 + [120.0]

        holding_a = self._priced_holding(quantity=10, avg_cost_price=100)  # value 1000
        holding_b = self._priced_holding(quantity=10, avg_cost_price=100)  # value 1000

        result = compute_portfolio_momentum(
            [holding_a, holding_b],
            {holding_a.id: flat_closes, holding_b.id: trending_closes},
        )
        b_momentum = compute_momentum_return(trending_closes)
        assert result == round(b_momentum / 2, 4)


class TestScalarDiff:
    def test_delta_is_b_minus_a(self):
        assert compute_scalar_diff(10.0, 15.0) == {"a": 10.0, "b": 15.0, "delta": 5.0}

    def test_negative_delta(self):
        assert compute_scalar_diff(15.0, 10.0) == {"a": 15.0, "b": 10.0, "delta": -5.0}

    def test_delta_none_when_a_is_none(self):
        result = compute_scalar_diff(None, 10.0)
        assert result == {"a": None, "b": 10.0, "delta": None}

    def test_delta_none_when_b_is_none(self):
        result = compute_scalar_diff(10.0, None)
        assert result == {"a": 10.0, "b": None, "delta": None}

    def test_delta_none_when_both_none(self):
        assert compute_scalar_diff(None, None) == {"a": None, "b": None, "delta": None}


class TestAllocationDiff:
    def test_shared_sectors_diffed_directly(self):
        diff = compute_allocation_diff({"Financials": 0.6}, {"Financials": 0.4})
        assert diff == {"Financials": {"a": 0.6, "b": 0.4, "delta": -0.2}}

    def test_sector_missing_from_one_side_defaults_to_zero(self):
        # Absence is a known fact (0% of that portfolio), not missing data —
        # unlike volatility's None-when-uncomputable convention.
        diff = compute_allocation_diff({"Financials": 1.0}, {"IT": 1.0})
        assert diff == {
            "Financials": {"a": 1.0, "b": 0.0, "delta": -1.0},
            "IT": {"a": 0.0, "b": 1.0, "delta": 1.0},
        }

    def test_both_empty(self):
        assert compute_allocation_diff({}, {}) == {}

    def test_none_side_is_unknown_not_zero(self):
        # A whole side of None means "no snapshot at all" (portfolio_comparison_service
        # signals this via total_value being None) — distinct from a real snapshot
        # that simply holds 0% of some sector. Must not read as a fabricated "confirmed
        # zero everywhere."
        diff = compute_allocation_diff({"Financials": 1.0}, None)
        assert diff == {"Financials": {"a": 1.0, "b": None, "delta": None}}

    def test_both_none(self):
        assert compute_allocation_diff(None, None) == {}


class TestHealthDiff:
    def _health(self, **overrides) -> dict:
        base = {
            "diversification_score": 0.7,
            "sector_concentration_hhi": 0.3,
            "portfolio_age_days": 100,
            "holding_count": 10,
            "volatility": 0.2,
        }
        base.update(overrides)
        return base

    def test_diffs_every_field(self):
        diff = compute_health_diff(self._health(), self._health(holding_count=14, volatility=0.25))
        assert diff["holding_count"] == {"a": 10, "b": 14, "delta": 4}
        assert diff["volatility"] == {"a": 0.2, "b": 0.25, "delta": pytest.approx(0.05)}
        assert diff["diversification_score"] == {"a": 0.7, "b": 0.7, "delta": 0.0}

    def test_none_when_either_side_has_no_snapshot_yet(self):
        diff = compute_health_diff(None, self._health())
        for field in (
            "diversification_score",
            "sector_concentration_hhi",
            "portfolio_age_days",
            "holding_count",
            "volatility",
        ):
            assert diff[field]["a"] is None
            assert diff[field]["delta"] is None

    def test_missing_volatility_key_treated_as_none(self):
        # Pre-ADR-024 snapshots have no "volatility" key at all.
        legacy_health = {
            "diversification_score": 0.7,
            "sector_concentration_hhi": 0.3,
            "portfolio_age_days": 100,
            "holding_count": 10,
        }
        diff = compute_health_diff(legacy_health, self._health())
        assert diff["volatility"] == {"a": None, "b": 0.2, "delta": None}
