"""Tests for app/services/sync_service.py's run_sync.

No dedicated test file existed for this module before Milestone 5 — it was
only exercised indirectly (smoke_test.py, and test_broker_connections.py's
mocked .delay()). Added now because run_sync gained real new logic (ADR-024's
historical-price fetch), which is exactly the kind of thing worth a direct
test rather than leaving covered only by inference.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest

from app.extensions import db
from app.integrations.broker.base import BrokerAPIError, RawHolding, TokenPair
from app.models.broker_connection import BrokerConnection
from app.models.holding import Holding
from app.models.portfolio import Portfolio
from app.models.portfolio_snapshot import PortfolioSnapshot
from app.models.user import User
from app.services.encryption_service import encrypt_token
from app.services.sync_service import run_sync

# 25 varying closes — enough to clear compute_volatility's minimum data-point floor.
_VARYING_CLOSES = [100.0, 102.0, 98.0, 101.0, 97.0] * 5


class _FakeAdapter:
    def __init__(self, historical_prices_by_isin=None, raise_for_isin=None):
        self._historical_prices_by_isin = historical_prices_by_isin or {}
        self._raise_for_isin = raise_for_isin or set()

    def fetch_holdings(self, access_token):
        return [
            RawHolding(
                symbol="RELIANCE",
                isin="INE002A01018",
                exchange="NSE",
                quantity=10.0,
                avg_cost_price=2500.0,
            ),
            RawHolding(
                symbol="TCS",
                isin="INE467B01029",
                exchange="NSE",
                quantity=5.0,
                avg_cost_price=3600.0,
            ),
        ]

    def fetch_historical_prices(self, access_token, isin, exchange, from_date, to_date):
        if isin in self._raise_for_isin:
            raise BrokerAPIError("simulated historical-price fetch failure")

        class _Point:
            def __init__(self, trade_date, close):
                self.trade_date = trade_date
                self.close = close

        closes = self._historical_prices_by_isin.get(isin, [])
        return [
            _Point(from_date + timedelta(days=i), close) for i, close in enumerate(closes)
        ]


def _make_connection(email: str) -> BrokerConnection:
    user = User(email=email, username=email.split("@")[0], password_hash="x")
    db.session.add(user)
    db.session.flush()

    connection = BrokerConnection(
        user_id=user.id,
        broker_name="upstox",
        connection_method="broker_api",
        access_token_encrypted=encrypt_token("fake-token"),
        status="active",
        token_expires_at=datetime.now(UTC) + timedelta(days=1),
    )
    db.session.add(connection)
    db.session.commit()
    return connection


@pytest.fixture(autouse=True)
def mock_discovery_cache(monkeypatch):
    """run_sync calls invalidate_discovery_cache(), which touches Redis —
    faked here the same way test_discovery.py fakes it."""
    monkeypatch.setattr("app.services.sync_service.invalidate_discovery_cache", MagicMock())


class TestRunSync:
    def test_creates_portfolio_and_holdings_on_first_sync(self, monkeypatch):
        connection = _make_connection("sync-basic@example.com")
        monkeypatch.setattr(
            "app.services.sync_service.get_adapter", lambda name: _FakeAdapter()
        )

        run_sync(str(connection.id))

        portfolio = Portfolio.query.filter_by(user_id=connection.user_id).first()
        assert portfolio is not None
        assert Holding.query.filter_by(portfolio_id=portfolio.id).count() == 2

        snapshot = PortfolioSnapshot.query.filter_by(portfolio_id=portfolio.id).first()
        assert snapshot.health_metrics["volatility"] is None  # fake returns no prices by default

    def test_computes_volatility_when_adapter_provides_price_history(self, monkeypatch):
        connection = _make_connection("sync-volatility@example.com")
        adapter = _FakeAdapter(
            historical_prices_by_isin={
                "INE002A01018": _VARYING_CLOSES,
                "INE467B01029": _VARYING_CLOSES,
            }
        )
        monkeypatch.setattr("app.services.sync_service.get_adapter", lambda name: adapter)

        run_sync(str(connection.id))

        portfolio = Portfolio.query.filter_by(user_id=connection.user_id).first()
        snapshot = PortfolioSnapshot.query.filter_by(portfolio_id=portfolio.id).first()
        assert snapshot.health_metrics["volatility"] is not None
        assert snapshot.health_metrics["volatility"] > 0

    def test_one_holdings_price_fetch_failure_does_not_fail_the_sync(self, monkeypatch):
        connection = _make_connection("sync-partial-failure@example.com")
        adapter = _FakeAdapter(
            historical_prices_by_isin={"INE467B01029": _VARYING_CLOSES},
            raise_for_isin={"INE002A01018"},  # RELIANCE's fetch blows up
        )
        monkeypatch.setattr("app.services.sync_service.get_adapter", lambda name: adapter)

        run_sync(str(connection.id))  # must not raise

        portfolio = Portfolio.query.filter_by(user_id=connection.user_id).first()
        assert portfolio is not None
        assert Holding.query.filter_by(portfolio_id=portfolio.id).count() == 2
        snapshot = PortfolioSnapshot.query.filter_by(portfolio_id=portfolio.id).first()
        # TCS alone still had enough data to produce a real figure.
        assert snapshot.health_metrics["volatility"] is not None

    def test_two_syncs_the_same_day_append_two_snapshots(self, monkeypatch):
        """ADR-025 — run_sync always inserts; it never checks for or updates
        an existing same-date row. Two manual syncs on the same calendar day
        (the cooldown permitting) must produce two distinct snapshot rows,
        not one overwritten in place."""
        connection = _make_connection("sync-same-day@example.com")
        monkeypatch.setattr(
            "app.services.sync_service.get_adapter", lambda name: _FakeAdapter()
        )

        run_sync(str(connection.id))
        run_sync(str(connection.id))

        portfolio = Portfolio.query.filter_by(user_id=connection.user_id).first()
        snapshots = PortfolioSnapshot.query.filter_by(portfolio_id=portfolio.id).all()
        assert len(snapshots) == 2
        # Both snapshots share a snapshot_date (both ran "today"); created_at
        # is what tells them apart chronologically.
        assert snapshots[0].snapshot_date == snapshots[1].snapshot_date
        assert snapshots[0].created_at != snapshots[1].created_at
