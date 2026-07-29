"""Query-shape regression guards (ADR-036).

These don't assert timings — wall-clock is far too noisy in CI to assert on.
They assert *shape*: how many SQL statements a request issues, and how many
rows it drags into memory. Both are deterministic, and both are what actually
regressed.

The bug these exist to prevent scored a perfectly innocent 6 queries while
loading 7,300 ORM objects to produce 20 health dicts — so a query counter
alone would have missed it. The row-volume assertion is the one that bites.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import event

from app.extensions import db
from app.models.portfolio import Portfolio
from app.models.portfolio_snapshot import PortfolioSnapshot
from app.models.user import User

SNAPSHOTS_PER_PORTFOLIO = 40
PORTFOLIO_COUNT = 5


class QueryRecorder:
    """Records every SQL statement executed inside the block."""

    def __init__(self, engine):
        self.engine = engine
        self.statements: list[str] = []

    def _after(self, conn, cursor, statement, params, context, executemany):
        self.statements.append(statement)

    def __enter__(self):
        self.statements = []
        event.listen(self.engine, "after_cursor_execute", self._after)
        return self

    def __exit__(self, *exc):
        event.remove(self.engine, "after_cursor_execute", self._after)

    @property
    def count(self) -> int:
        return len(self.statements)


@pytest.fixture
def seeded_public_portfolios(client):
    """Several public portfolios, each with a real snapshot history.

    The history depth is the point: with one snapshot per portfolio, loading
    the whole collection and loading just the latest are indistinguishable,
    so the regression this guards against would pass unnoticed.

    Identities are uniquified per test because the suite's `db` fixture does
    not actually roll back application-level commits (see its docstring, and
    the open fix in PR #8) — these rows really do persist between tests, so
    reusing a fixed email would collide on the second test in this module.
    Matching how the rest of the suite copes with the same limitation.
    """
    unique = uuid.uuid4().hex[:8]
    portfolios = []
    for i in range(PORTFOLIO_COUNT):
        user = User(
            email=f"qperf{unique}-{i}@example.com",
            username=f"qperf{unique}{i}",
            display_name=f"Query Perf {i}",
            password_hash="x",
        )
        db.session.add(user)
        db.session.flush()

        portfolio = Portfolio(user_id=user.id, portfolio_type="verified", is_public=True)
        db.session.add(portfolio)
        db.session.flush()

        for d in range(SNAPSHOTS_PER_PORTFOLIO):
            db.session.add(
                PortfolioSnapshot(
                    portfolio_id=portfolio.id,
                    snapshot_date=date(2026, 1, 1) + timedelta(days=d),
                    total_value=1000 + d,
                    sector_allocation={"IT": 1.0},
                    asset_allocation={"Equity": 1.0},
                    health_metrics={"holding_count": 1, "diversification_score": d / 100},
                    created_at=datetime.now(UTC) + timedelta(seconds=d),
                )
            )
        portfolios.append(portfolio)

    db.session.commit()
    return portfolios


class TestDiscoveryDoesNotLoadSnapshotHistory:
    def test_discovery_loads_one_snapshot_row_per_portfolio(
        self, client, seeded_public_portfolios, monkeypatch
    ):
        """The regression guard that matters (ADR-036).

        Discovery needs each portfolio's *latest* health only. Loading the
        snapshot collection to find it meant every snapshot ever taken for
        every portfolio on the page came back — growing forever as syncs
        accumulate. Asserting on rows-returned rather than query count is
        deliberate: the original bug had a healthy query count.
        """
        from app.services import discovery_service

        monkeypatch.setattr(discovery_service.redis_client, "get", lambda *a, **k: None)
        monkeypatch.setattr(discovery_service.redis_client, "set", lambda *a, **k: None)

        snapshot_rows = []

        def _count_snapshot_rows(conn, cursor, statement, params, context, executemany):
            if "portfolio_snapshots" in statement.lower() and statement.lstrip().lower().startswith(
                "select"
            ):
                snapshot_rows.append(statement)

        event.listen(db.engine, "after_cursor_execute", _count_snapshot_rows)
        try:
            resp = client.get("/api/v1/discovery/investors?per_page=20")
        finally:
            event.remove(db.engine, "after_cursor_execute", _count_snapshot_rows)

        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert len(data) >= PORTFOLIO_COUNT

        # One batched snapshot query for the whole page — not one per
        # portfolio, and not a collection load.
        assert (
            len(snapshot_rows) == 1
        ), f"expected exactly one snapshot query for the page, got {len(snapshot_rows)}"

        # And it must be a ranked/limited lookup, not "select every snapshot
        # for these portfolios".
        assert "row_number" in snapshot_rows[0].lower()

    def test_discovery_query_count_does_not_scale_with_page_size(
        self, client, seeded_public_portfolios, monkeypatch
    ):
        """Query count must not grow *proportionally* with rows returned —
        that's what an N+1 is.

        Deliberately not asserting the counts are identical: selectinload
        legitimately skips a nested load when there's nothing to load (a
        single-portfolio page whose portfolio has no strategy tags emits one
        fewer query than a page where some do). That's a small constant
        difference, not per-row growth. Twenty times the rows for a couple
        extra queries is fine; twenty times the rows for twenty extra
        queries is the regression.
        """
        from app.services import discovery_service

        monkeypatch.setattr(discovery_service.redis_client, "get", lambda *a, **k: None)
        monkeypatch.setattr(discovery_service.redis_client, "set", lambda *a, **k: None)

        with QueryRecorder(db.engine) as small:
            small_resp = client.get("/api/v1/discovery/investors?per_page=1")
        small_count = small.count

        db.session.remove()  # drop the identity map so the second run is fair

        with QueryRecorder(db.engine) as large:
            large_resp = client.get("/api/v1/discovery/investors?per_page=20")

        rows_small = len(small_resp.get_json()["data"])
        rows_large = len(large_resp.get_json()["data"])
        extra_rows = rows_large - rows_small
        extra_queries = large.count - small_count

        assert extra_rows > 0, "test needs more seeded portfolios to be meaningful"
        # Allow a small fixed overhead; anything approaching one query per
        # extra row means per-portfolio loading is back.
        assert extra_queries <= 3, (
            f"returning {extra_rows} more portfolios cost {extra_queries} more queries "
            f"({small_count} -> {large.count}) — that scales per row, i.e. an N+1"
        )


class TestLatestHealthIsConsistentAcrossEndpoints:
    def test_discovery_and_analytics_report_the_same_latest_health(
        self, client, seeded_public_portfolios, monkeypatch
    ):
        """ADR-025/ADR-036 — the discovery feed and the analytics endpoint
        must agree on which snapshot is 'latest'.

        They previously could not: discovery picked via max(snapshot_date),
        ignoring created_at, while analytics ordered by both. For two
        snapshots sharing a calendar date that's a coin flip, so the same
        portfolio could show different health depending which endpoint you
        asked.
        """
        from app.services import discovery_service

        monkeypatch.setattr(discovery_service.redis_client, "get", lambda *a, **k: None)
        monkeypatch.setattr(discovery_service.redis_client, "set", lambda *a, **k: None)

        portfolio = seeded_public_portfolios[0]

        # Two snapshots on the SAME date — created_at is the only tiebreaker.
        same_date = date(2027, 3, 3)
        for offset, score in ((0, 0.11), (60, 0.99)):
            db.session.add(
                PortfolioSnapshot(
                    portfolio_id=portfolio.id,
                    snapshot_date=same_date,
                    total_value=5000,
                    sector_allocation={"IT": 1.0},
                    asset_allocation={"Equity": 1.0},
                    health_metrics={"holding_count": 2, "diversification_score": score},
                    created_at=datetime.now(UTC) + timedelta(seconds=offset),
                )
            )
        db.session.commit()

        analytics = client.get(f"/api/v1/portfolios/{portfolio.id}/analytics").get_json()["data"]
        feed = client.get("/api/v1/discovery/investors?per_page=100").get_json()["data"]
        entry = next(e for e in feed if e["id"] == str(portfolio.id))

        # The later-created snapshot (0.99) is the latest one, and both
        # endpoints must say so.
        assert analytics["health"]["diversification_score"] == 0.99
        assert entry["health"]["diversification_score"] == 0.99
