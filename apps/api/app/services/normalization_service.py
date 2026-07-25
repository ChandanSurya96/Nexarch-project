"""Normalize broker-specific raw holdings into the internal Holding shape.

See docs/database.md HOLDINGS entity and docs/broker-integrations.md "Data
Mapping" — every adapter's RawHolding list passes through here so the rest of
the system (analytics, discovery, public profiles) never needs to know which
broker/AA source a holding came from (docs/architecture.md "Data Flow").
"""

from __future__ import annotations

from datetime import date

from app.data.sector_mapping import enrich
from app.integrations.broker.base import RawHolding


def normalize_holding(raw: RawHolding, as_of_date: date) -> dict:
    """Map one RawHolding into the fields Holding.__init__ expects.

    Sector/market-cap enrichment happens here (not in the adapter) since it's
    broker-independent reference data, not something any broker's API
    provides (see docs/broker-integrations.md).
    """
    enrichment = enrich(raw.isin)
    return {
        "symbol": raw.symbol,
        "isin": raw.isin,
        "exchange": raw.exchange,
        "quantity": raw.quantity,
        "avg_cost_price": raw.avg_cost_price,
        "sector": enrichment["sector"],
        "market_cap_category": enrichment["market_cap_category"],
        "as_of_date": as_of_date,
    }


def normalize_holdings(raw_holdings: list[RawHolding], as_of_date: date) -> list[dict]:
    return [normalize_holding(raw, as_of_date) for raw in raw_holdings]
