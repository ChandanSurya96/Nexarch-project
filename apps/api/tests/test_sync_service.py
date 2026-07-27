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
from app.integrations.broker.base import (
    BrokerAPIError,
    BrokerRateLimitError,
    BrokerTokenExpiredError,
    RawHolding,
)
from app.models.audit_log import AuditLog
from app.models.broker_connection import BrokerConnection
from app.models.holding import Holding
from app.models.portfolio import Portfolio
from app.models.portfolio_snapshot import PortfolioSnapshot
from app.models.strategy_category import StrategyCategory
from app.models.user import User
from app.services.encryption_service import encrypt_token
from app.services.sync_service import run_sync

# 25 varying closes — enough to clear compute_volatility's minimum data-point floor.
_VARYING_CLOSES = [100.0, 102.0, 98.0, 101.0, 97.0] * 5

# 64 flat closes — zero volatility (well under the 15% Low-risk threshold)
# and zero momentum (well under the 10% Momentum threshold): isolates Low-risk.
_FLAT_CLOSES_64 = [100.0] * 64

# 64 closes trending steadily upward ~31.5% overall — clears the 10%
# Momentum threshold.
_TRENDING_CLOSES_64 = [100.0 + i * 0.5 for i in range(64)]


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
        return [_Point(from_date + timedelta(days=i), close) for i, close in enumerate(closes)]


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
        monkeypatch.setattr("app.services.sync_service.get_adapter", lambda name: _FakeAdapter())

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
        monkeypatch.setattr("app.services.sync_service.get_adapter", lambda name: _FakeAdapter())

        run_sync(str(connection.id))
        run_sync(str(connection.id))

        portfolio = Portfolio.query.filter_by(user_id=connection.user_id).first()
        snapshots = PortfolioSnapshot.query.filter_by(portfolio_id=portfolio.id).all()
        assert len(snapshots) == 2
        # Both snapshots share a snapshot_date (both ran "today"); created_at
        # is what tells them apart chronologically.
        assert snapshots[0].snapshot_date == snapshots[1].snapshot_date
        assert snapshots[0].created_at != snapshots[1].created_at


class TestRunSyncFailureBranches:
    """ADR-034 — every failure branch must be consistent: connection.status
    set, an audit_logs "error" event written, and (for the two branches
    Celery can retry) the exception re-raised so autoretry_for actually
    sees it."""

    def _error_events(self, user_id) -> list[AuditLog]:
        return AuditLog.query.filter_by(user_id=user_id, event_type="error").all()

    def test_token_expired_marks_status_and_audits_without_raising(self, monkeypatch):
        connection = _make_connection("sync-expired@example.com")

        class _ExpiredAdapter:
            def fetch_holdings(self, access_token):
                raise BrokerTokenExpiredError("token expired")

        monkeypatch.setattr("app.services.sync_service.get_adapter", lambda name: _ExpiredAdapter())

        run_sync(str(connection.id))  # must not raise

        db.session.refresh(connection)
        assert connection.status == "expired"
        events = self._error_events(connection.user_id)
        assert len(events) == 1
        assert events[0].event_metadata["reason"] == "token_expired"

    def test_api_error_marks_status_and_audits_without_raising(self, monkeypatch):
        connection = _make_connection("sync-api-error@example.com")

        class _ApiErrorAdapter:
            def fetch_holdings(self, access_token):
                raise BrokerAPIError("some non-rate-limit API failure")

        monkeypatch.setattr(
            "app.services.sync_service.get_adapter", lambda name: _ApiErrorAdapter()
        )

        run_sync(str(connection.id))  # must not raise — not retried, unlike rate limit

        db.session.refresh(connection)
        assert connection.status == "error"
        assert len(self._error_events(connection.user_id)) == 1

    def test_rate_limit_non_final_attempt_reraises_without_touching_status_or_audit(
        self, monkeypatch
    ):
        """A retry Celery still has attempts left for — marking the
        connection "error" here would flip status back to "active" on a
        successful retry, and leave a spurious audit row for what turns out
        to be a successful sync."""
        connection = _make_connection("sync-rate-limit-retry@example.com")

        class _RateLimitAdapter:
            def fetch_holdings(self, access_token):
                raise BrokerRateLimitError("rate limited")

        monkeypatch.setattr(
            "app.services.sync_service.get_adapter", lambda name: _RateLimitAdapter()
        )

        with pytest.raises(BrokerRateLimitError):
            run_sync(str(connection.id), is_final_attempt=False)

        db.session.refresh(connection)
        assert connection.status == "active"  # unchanged
        assert len(self._error_events(connection.user_id)) == 0

    def test_rate_limit_final_attempt_marks_status_and_audits_then_reraises(self, monkeypatch):
        connection = _make_connection("sync-rate-limit-final@example.com")

        class _RateLimitAdapter:
            def fetch_holdings(self, access_token):
                raise BrokerRateLimitError("rate limited")

        monkeypatch.setattr(
            "app.services.sync_service.get_adapter", lambda name: _RateLimitAdapter()
        )

        with pytest.raises(BrokerRateLimitError):
            run_sync(str(connection.id), is_final_attempt=True)

        db.session.refresh(connection)
        assert connection.status == "error"
        assert len(self._error_events(connection.user_id)) == 1

    def test_unexpected_exception_after_fetch_marks_status_audits_and_reraises(self, monkeypatch):
        """The previously-uncaught tail — anything past a successful
        fetch_holdings that isn't one of the three known broker-error
        types. Must not be silent: this used to leave connection.status
        stale and write no audit event at all."""
        connection = _make_connection("sync-unexpected-error@example.com")
        monkeypatch.setattr("app.services.sync_service.get_adapter", lambda name: _FakeAdapter())
        monkeypatch.setattr(
            "app.services.sync_service.normalize_holdings",
            MagicMock(side_effect=RuntimeError("boom")),
        )

        with pytest.raises(RuntimeError):
            run_sync(str(connection.id))

        db.session.refresh(connection)
        assert connection.status == "error"
        events = self._error_events(connection.user_id)
        assert len(events) == 1
        assert events[0].event_metadata["reason"] == "unexpected_error"


class TestStrategyTagging:
    """Milestone 7, ADR-028 — strategy tags recomputed alongside health
    metrics every sync."""

    def _tag_slugs(self, portfolio_id) -> set[str]:
        from app.models.strategy_category import PortfolioStrategyTag

        tags = PortfolioStrategyTag.query.filter_by(portfolio_id=portfolio_id).all()
        return {tag.strategy_category.slug for tag in tags}

    def test_ensures_strategy_category_rows_exist_regardless_of_prior_state(self, monkeypatch):
        # Doesn't assume a pristine DB (other test modules may have already
        # committed these rows within the same test session — see
        # test_discovery.py's TestStrategyCategories note) — just confirms
        # run_sync never fails for lack of them, and all 8 exist afterward.
        connection = _make_connection("sync-no-categories-yet@example.com")
        monkeypatch.setattr("app.services.sync_service.get_adapter", lambda name: _FakeAdapter())

        run_sync(str(connection.id))  # must not raise

        assert StrategyCategory.query.count() == 8

    def test_creates_low_risk_tag_when_volatility_is_low(self, monkeypatch):
        connection = _make_connection("sync-low-risk@example.com")
        adapter = _FakeAdapter(
            historical_prices_by_isin={
                "INE002A01018": _FLAT_CLOSES_64,
                "INE467B01029": _FLAT_CLOSES_64,
            }
        )
        monkeypatch.setattr("app.services.sync_service.get_adapter", lambda name: adapter)

        run_sync(str(connection.id))

        portfolio = Portfolio.query.filter_by(user_id=connection.user_id).first()
        assert "low-risk" in self._tag_slugs(portfolio.id)

    def test_creates_momentum_tag_when_trend_is_strong(self, monkeypatch):
        connection = _make_connection("sync-momentum@example.com")
        adapter = _FakeAdapter(
            historical_prices_by_isin={
                "INE002A01018": _TRENDING_CLOSES_64,
                "INE467B01029": _TRENDING_CLOSES_64,
            }
        )
        monkeypatch.setattr("app.services.sync_service.get_adapter", lambda name: adapter)

        run_sync(str(connection.id))

        portfolio = Portfolio.query.filter_by(user_id=connection.user_id).first()
        assert "momentum" in self._tag_slugs(portfolio.id)

    def test_second_sync_replaces_tags_rather_than_accumulating(self, monkeypatch):
        connection = _make_connection("sync-tag-replace@example.com")
        low_risk_adapter = _FakeAdapter(
            historical_prices_by_isin={
                "INE002A01018": _FLAT_CLOSES_64,
                "INE467B01029": _FLAT_CLOSES_64,
            }
        )
        monkeypatch.setattr("app.services.sync_service.get_adapter", lambda name: low_risk_adapter)
        run_sync(str(connection.id))

        portfolio = Portfolio.query.filter_by(user_id=connection.user_id).first()
        assert "low-risk" in self._tag_slugs(portfolio.id)

        # Re-sync with no price history at all -> volatility/momentum both
        # None -> no tags should match anymore, and the old "low-risk" row
        # must be gone, not left behind alongside nothing new.
        no_price_adapter = _FakeAdapter()
        monkeypatch.setattr("app.services.sync_service.get_adapter", lambda name: no_price_adapter)
        run_sync(str(connection.id))

        assert self._tag_slugs(portfolio.id) == set()
