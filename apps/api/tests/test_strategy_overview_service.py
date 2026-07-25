"""Tests for app/services/strategy_overview_service.py.

Per docs/product-requirements.md and docs/security.md: copy must be
descriptive only, never a recommendation or a promise of returns.
"""

from datetime import date

from app.models.holding import Holding
from app.services.strategy_overview_service import generate_overview


def _holding(sector: str, quantity: float, avg_cost_price: float, market_cap: str) -> Holding:
    return Holding(
        symbol="TEST",
        sector=sector,
        quantity=quantity,
        avg_cost_price=avg_cost_price,
        market_cap_category=market_cap,
        as_of_date=date(2026, 7, 25),
    )


_NON_DESCRIPTIVE_PHRASES = [
    "you should",
    "buy",
    "sell now",
    "guaranteed",
    "will return",
    "recommend",
]


class TestGenerateOverview:
    def test_no_data_returns_none(self):
        assert generate_overview({}, 0.0, []) is None

    def test_high_concentration_phrasing(self):
        holdings = [_holding("Financials", 10, 100, "large")]
        overview = generate_overview({"Financials": 1.0}, 1.0, holdings)
        assert overview is not None
        assert "concentrated in Financials" in overview
        assert "large-cap" in overview

    def test_moderate_concentration_phrasing(self):
        holdings = [_holding("Financials", 10, 100, "large")]
        overview = generate_overview(
            {"Financials": 0.4, "IT": 0.3, "Consumer": 0.3}, 0.34, holdings
        )
        assert "weighted toward Financials" in overview

    def test_low_concentration_phrasing(self):
        holdings = [_holding("Financials", 10, 100, "large")]
        allocation = {"Financials": 0.25, "IT": 0.25, "Consumer": 0.25, "Energy": 0.25}
        overview = generate_overview(allocation, 0.25, holdings)
        assert "diversified across sectors including" in overview

    def test_no_dominant_market_cap_omits_phrase(self):
        holdings = [
            _holding("Financials", 10, 100, "large"),
            _holding("Financials", 10, 100, "small"),
        ]
        overview = generate_overview({"Financials": 1.0}, 1.0, holdings)
        assert "predominantly" not in overview

    def test_never_reads_as_advice_or_promise(self):
        holdings = [_holding("Financials", 10, 100, "large")]
        for allocation, hhi in [
            ({"Financials": 1.0}, 1.0),
            ({"Financials": 0.4, "IT": 0.6}, 0.52),
            ({"Financials": 0.25, "IT": 0.25, "Consumer": 0.25, "Energy": 0.25}, 0.25),
        ]:
            overview = generate_overview(allocation, hhi, holdings)
            lowered = overview.lower()
            for phrase in _NON_DESCRIPTIVE_PHRASES:
                assert phrase not in lowered
