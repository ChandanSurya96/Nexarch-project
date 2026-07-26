"""Sync orchestration — fetch, normalize, upsert, recompute, categorize, log.

See docs/architecture.md "Data Flow: Portfolio Sync". Called by the Celery
task in app/tasks/sync.py — kept as a plain function here (no Celery/Flask
import beyond db) so it's unit-testable without a running worker.

Strategy-category tags (Milestone 7) are recomputed here alongside health
metrics — see app/services/strategy_categorization_service.py.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta

from app.extensions import db
from app.integrations.broker.base import (
    BrokerAdapter,
    BrokerAPIError,
    BrokerRateLimitError,
    BrokerTokenExpiredError,
)
from app.integrations.broker.registry import get_adapter
from app.models.broker_connection import BrokerConnection
from app.models.holding import Holding
from app.models.portfolio import Portfolio
from app.models.portfolio_snapshot import PortfolioSnapshot
from app.models.strategy_category import PortfolioStrategyTag
from app.services import audit_service
from app.services.analytics_service import (
    compute_asset_allocation,
    compute_health_metrics,
    compute_sector_allocation,
    compute_total_value,
)
from app.services.discovery_service import invalidate_discovery_cache
from app.services.encryption_service import decrypt_token
from app.services.normalization_service import normalize_holdings
from app.services.strategy_categorization_service import categorize, ensure_strategy_category_rows

# Trailing window for the volatility calculation (ADR-024) — about a year of
# trading history, a conventional lookback for an annualized figure.
_VOLATILITY_LOOKBACK_DAYS = 365


def _fetch_closes_by_holding_id(
    adapter: BrokerAdapter, access_token: str, holdings: list[Holding]
) -> dict[uuid.UUID, list[float]]:
    """Best-effort per-holding historical closes for compute_portfolio_volatility.

    One holding's fetch failing (bad/missing ISIN, rate limit, no historical
    data for that instrument) doesn't fail the sync — it just doesn't
    contribute to the portfolio volatility figure, same "partial honesty
    over all-or-nothing" posture as the rest of this module.
    """
    to_date = date.today()
    from_date = to_date - timedelta(days=_VOLATILITY_LOOKBACK_DAYS)
    closes_by_holding_id: dict[uuid.UUID, list[float]] = {}

    for holding in holdings:
        if not holding.isin or not holding.exchange:
            continue
        try:
            points = adapter.fetch_historical_prices(
                access_token, holding.isin, holding.exchange, from_date, to_date
            )
        except (BrokerTokenExpiredError, BrokerRateLimitError, BrokerAPIError):
            continue
        if points:
            closes_by_holding_id[holding.id] = [
                point.close for point in sorted(points, key=lambda p: p.trade_date)
            ]

    return closes_by_holding_id


def run_sync(broker_connection_id: str) -> None:
    """Run one sync cycle for a single broker connection.

    Handles token-expiry and generic-API failures distinctly (see
    docs/broker-integrations.md "Refresh Strategy") and always writes an
    audit_logs entry (see docs/security.md).
    """
    connection = db.session.get(BrokerConnection, uuid.UUID(str(broker_connection_id)))
    if connection is None:
        return  # disconnected/deleted before this task ran — nothing to sync

    adapter = get_adapter(connection.broker_name)

    try:
        access_token = decrypt_token(connection.access_token_encrypted)
        raw_holdings = adapter.fetch_holdings(access_token)
    except BrokerTokenExpiredError:
        connection.status = "expired"
        db.session.commit()
        audit_service.log_event(
            connection.user_id,
            "error",
            {"broker_connection_id": str(connection.id), "reason": "token_expired"},
        )
        return
    except (BrokerRateLimitError, BrokerAPIError) as exc:
        connection.status = "error"
        db.session.commit()
        audit_service.log_event(
            connection.user_id,
            "error",
            {"broker_connection_id": str(connection.id), "reason": str(exc)},
        )
        return

    as_of = date.today()
    normalized = normalize_holdings(raw_holdings, as_of)

    portfolio = connection.portfolio
    if portfolio is None:
        portfolio = Portfolio(
            user_id=connection.user_id,
            broker_connection_id=connection.id,
            portfolio_type="verified",
        )
        db.session.add(portfolio)
        db.session.flush()  # assign portfolio.id before holdings reference it

    # Portfolio age must be computed from snapshot history that predates this
    # sync's own snapshot (see docs/product-requirements.md) — query first.
    prior_snapshots = PortfolioSnapshot.query.filter_by(portfolio_id=portfolio.id).all()

    # Holdings are point-in-time, overwritten on each sync (see docs/database.md).
    Holding.query.filter_by(portfolio_id=portfolio.id).delete()
    holdings = [Holding(portfolio_id=portfolio.id, **fields) for fields in normalized]
    db.session.add_all(holdings)
    db.session.flush()

    closes_by_holding_id = _fetch_closes_by_holding_id(adapter, access_token, holdings)

    sector_allocation = compute_sector_allocation(holdings)
    asset_allocation = compute_asset_allocation(holdings)
    health_metrics = compute_health_metrics(holdings, prior_snapshots, closes_by_holding_id)
    total_value = compute_total_value(holdings)

    snapshot = PortfolioSnapshot(
        portfolio_id=portfolio.id,
        snapshot_date=as_of,
        total_value=total_value,
        sector_allocation=sector_allocation,
        asset_allocation=asset_allocation,
        health_metrics=health_metrics,
    )
    db.session.add(snapshot)

    # Strategy tags recomputed fresh every sync (Milestone 7, ADR-028) — same
    # delete+reinsert idempotent pattern already used for Holding rows above,
    # not an accumulating history. Public Investor Library portfolios never
    # go through run_sync, so their manually-curated tags are untouched.
    categories_by_slug = ensure_strategy_category_rows()
    PortfolioStrategyTag.query.filter_by(portfolio_id=portfolio.id).delete()
    for match in categorize(holdings, health_metrics):
        db.session.add(
            PortfolioStrategyTag(
                portfolio_id=portfolio.id,
                strategy_category_id=categories_by_slug[match["slug"]].id,
            )
        )

    connection.last_synced_at = datetime.now(UTC)
    connection.status = "active"
    db.session.commit()

    # A successful sync may have changed this portfolio's discovery-feed
    # standing (allocation, health, updated_at) — clear the cache so the
    # feed reflects it on next read (see docs/architecture.md "Caching Strategy").
    invalidate_discovery_cache()

    audit_service.log_event(
        connection.user_id,
        "sync",
        {"broker_connection_id": str(connection.id), "holding_count": len(holdings)},
    )
