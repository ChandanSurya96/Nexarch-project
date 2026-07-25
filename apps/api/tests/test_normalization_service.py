"""Tests for app/services/normalization_service.py."""

from datetime import date

from app.integrations.broker.base import RawHolding
from app.services.normalization_service import normalize_holding, normalize_holdings


class TestNormalizeHolding:
    def test_mapped_isin_gets_enriched(self):
        raw = RawHolding(
            symbol="RELIANCE",
            isin="INE002A01018",  # Reliance Industries — in sector_mapping.py
            exchange="NSE",
            quantity=10.0,
            avg_cost_price=2500.0,
        )
        result = normalize_holding(raw, date(2026, 7, 25))

        assert result["symbol"] == "RELIANCE"
        assert result["isin"] == "INE002A01018"
        assert result["exchange"] == "NSE"
        assert result["quantity"] == 10.0
        assert result["avg_cost_price"] == 2500.0
        assert result["sector"] == "Energy"
        assert result["market_cap_category"] == "large"
        assert result["as_of_date"] == date(2026, 7, 25)

    def test_unmapped_isin_gets_none_not_a_guess(self):
        raw = RawHolding(
            symbol="UNKNOWNCO",
            isin="INE999Z99999",  # not in sector_mapping.py
            exchange="NSE",
            quantity=5.0,
            avg_cost_price=100.0,
        )
        result = normalize_holding(raw, date(2026, 7, 25))

        assert result["sector"] is None
        assert result["market_cap_category"] is None

    def test_missing_isin_gets_none(self):
        raw = RawHolding(
            symbol="SOMESTOCK", isin=None, exchange="BSE", quantity=1.0, avg_cost_price=50.0
        )
        result = normalize_holding(raw, date(2026, 7, 25))

        assert result["sector"] is None
        assert result["market_cap_category"] is None


class TestNormalizeHoldings:
    def test_maps_list_and_shares_as_of_date(self):
        raw_holdings = [
            RawHolding("RELIANCE", "INE002A01018", "NSE", 10.0, 2500.0),
            RawHolding("TCS", "INE467B01029", "NSE", 5.0, 3500.0),
        ]
        results = normalize_holdings(raw_holdings, date(2026, 7, 25))

        assert len(results) == 2
        assert all(r["as_of_date"] == date(2026, 7, 25) for r in results)
        assert results[0]["sector"] == "Energy"
        assert results[1]["sector"] == "IT"

    def test_empty_list(self):
        assert normalize_holdings([], date(2026, 7, 25)) == []
