"""Endpoint benchmark harness — query counts + latency (Phase 2.5 Slice 3).

Run from the project root, with the apps/api venv active and Postgres+Redis
reachable (docker compose up -d):
    apps/api/venv/Scripts/python.exe scripts/benchmark_endpoints.py [label]
    apps/api/venv/bin/python scripts/benchmark_endpoints.py [label]

Why this exists: the dev database holds a handful of rows, which hides every
scaling problem the app has. The original discovery-feed regression this
slice fixed was invisible at dev volume and obvious at 21,900 snapshots. So
this seeds a *disposable* `nexarch_bench` database with a realistic year of
daily syncs and measures against that.

Reads DATABASE_URL only to derive the bench database name — it never touches
the dev database, and it DROPS AND RECREATES every table in `nexarch_bench`
on each run. Point it at nothing you care about.

Two numbers matter, and they answer different questions:
  * query count  — catches N+1s and redundant round-trips.
  * wall vs db   — catches ORM over-fetching. The discovery bug scored a
                   perfectly innocent 6 queries while spending ~95% of the
                   request instantiating 7,300 ORM objects; only the
                   wall-minus-db gap exposed it.

Compare runs by label:
    python scripts/benchmark_endpoints.py before
    ...make changes...
    python scripts/benchmark_endpoints.py after
Results are written to bench-<label>.json next to this script.
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "apps" / "api"))

BENCH_DB = "nexarch_bench"
os.environ.setdefault("FLASK_ENV", "development")
os.environ["DATABASE_URL"] = f"postgresql://nexarch:nexarch@localhost:5432/{BENCH_DB}"

from sqlalchemy import event  # noqa: E402

from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402

LABEL = sys.argv[1] if len(sys.argv) > 1 else "run"

# Scenario: a year of daily syncs for a modest user base. Big enough that
# per-row costs and unbounded collection loads become visible; small enough
# to seed in a few seconds.
N_PORTFOLIOS = 60
N_SNAPSHOTS_EACH = 365
N_HOLDINGS_EACH = 15
N_FOLLOWS = 40

SECTORS = ["IT", "Financials", "Energy", "Pharma", "FMCG", "Auto"]


class QueryCounter:
    """Counts SQL statements and total DB time for a block of work."""

    def __init__(self, engine):
        self.engine = engine
        self.count = 0
        self.db_seconds = 0.0
        self._t0 = None

    def _before(self, conn, cursor, statement, params, context, executemany):
        self._t0 = time.perf_counter()

    def _after(self, conn, cursor, statement, params, context, executemany):
        self.count += 1
        if self._t0 is not None:
            self.db_seconds += time.perf_counter() - self._t0

    def __enter__(self):
        self.count = 0
        self.db_seconds = 0.0
        event.listen(self.engine, "before_cursor_execute", self._before)
        event.listen(self.engine, "after_cursor_execute", self._after)
        return self

    def __exit__(self, *exc):
        event.remove(self.engine, "before_cursor_execute", self._before)
        event.remove(self.engine, "after_cursor_execute", self._after)


def seed(app):
    from app.models.follow import Follow
    from app.models.holding import Holding
    from app.models.portfolio import Portfolio
    from app.models.portfolio_snapshot import PortfolioSnapshot
    from app.models.strategy_category import PortfolioStrategyTag
    from app.models.user import User
    from app.services.strategy_categorization_service import (
        ensure_strategy_category_rows,
    )

    with app.app_context():
        db.drop_all()
        db.create_all()
        categories = ensure_strategy_category_rows()
        cat_ids = [c.id for c in categories.values()][:3]

        users = [
            User(
                email=f"bench{i}@example.com",
                username=f"bench{i}",
                display_name=f"Bench Investor {i}",
                password_hash="x",
            )
            for i in range(N_PORTFOLIOS)
        ]
        db.session.add_all(users)
        db.session.flush()

        portfolios = [
            Portfolio(user_id=u.id, portfolio_type="verified", is_public=True) for u in users
        ]
        db.session.add_all(portfolios)
        db.session.flush()

        holdings, snapshots, tags = [], [], []
        today = date.today()
        for p in portfolios:
            for h in range(N_HOLDINGS_EACH):
                holdings.append(
                    Holding(
                        portfolio_id=p.id,
                        symbol=f"SYM{h}",
                        isin=f"INE{h:09d}",
                        exchange="NSE",
                        quantity=10 + h,
                        avg_cost_price=100.0 + h,
                        sector=SECTORS[h % len(SECTORS)],
                        market_cap_category="large",
                        as_of_date=today,
                    )
                )
            for d in range(N_SNAPSHOTS_EACH):
                snapshots.append(
                    PortfolioSnapshot(
                        portfolio_id=p.id,
                        snapshot_date=today - timedelta(days=N_SNAPSHOTS_EACH - 1 - d),
                        total_value=100000.0 + d * 10,
                        sector_allocation={s: 1.0 / len(SECTORS) for s in SECTORS},
                        asset_allocation={"Equity": 1.0},
                        health_metrics={
                            "diversification_score": 0.8,
                            "sector_concentration_hhi": 0.2,
                            "portfolio_age_days": d,
                            "holding_count": N_HOLDINGS_EACH,
                            "volatility": 0.12,
                            "momentum": 0.05,
                        },
                        created_at=datetime.now(UTC) - timedelta(days=N_SNAPSHOTS_EACH - 1 - d),
                    )
                )
            for cid in cat_ids[:2]:
                tags.append(PortfolioStrategyTag(portfolio_id=p.id, strategy_category_id=cid))

        db.session.bulk_save_objects(holdings)
        db.session.bulk_save_objects(snapshots)
        db.session.bulk_save_objects(tags)
        db.session.commit()

        follower = users[0]
        db.session.add_all(
            [
                Follow(
                    follower_user_id=follower.id,
                    followed_portfolio_id=portfolios[i + 1].id,
                )
                for i in range(N_FOLLOWS)
            ]
        )
        db.session.commit()

        print(
            f"seeded: {N_PORTFOLIOS} portfolios, {N_PORTFOLIOS * N_SNAPSHOTS_EACH} snapshots, "
            f"{N_PORTFOLIOS * N_HOLDINGS_EACH} holdings, {N_FOLLOWS} follows"
        )
        return str(portfolios[0].id), str(portfolios[1].id), follower.email


def measure(counter, name, fn, rounds=5, setup=None):
    """Best-of-N wall time plus the query count for one endpoint.

    `setup` runs OUTSIDE the timed region — used for cache invalidation so
    Redis SCAN/DELETE cost isn't attributed to the endpoint under test.
    Best-of rather than mean: we're after the floor cost of the code path,
    not the machine's background noise. Even so, treat single-digit-ms
    differences as noise — only trust changes that also move the query count
    or are large enough to survive a re-run.
    """
    if setup:
        setup()
    fn()  # warm

    best, qc, dbt = None, 0, 0.0
    for _ in range(rounds):
        # Drop the SQLAlchemy identity map between rounds. Without this a
        # later round reuses objects loaded by an earlier one and issues
        # fewer queries, so the reported count depends on which round
        # happened to be fastest — which made counts vary run-to-run and
        # quietly understated the real per-request cost.
        db.session.remove()
        if setup:
            setup()
        with counter:
            t0 = time.perf_counter()
            fn()
            elapsed = time.perf_counter() - t0
        if best is None or elapsed < best:
            best, qc, dbt = elapsed, counter.count, counter.db_seconds

    print(f"{name:<34} {qc:>4} queries {best * 1000:>9.1f} ms  (db {dbt * 1000:>7.1f} ms)")
    return {
        "name": name,
        "queries": qc,
        "ms": round(best * 1000, 1),
        "db_ms": round(dbt * 1000, 1),
    }


def main():
    app = create_app()
    pid_a, pid_b, follower_email = seed(app)

    with app.app_context():
        from app.models.user import User
        from app.services import refresh_token_service
        from app.services.discovery_service import invalidate_discovery_cache

        counter = QueryCounter(db.engine)
        client = app.test_client()

        user = User.query.filter_by(email=follower_email).one()
        access_token, _ = refresh_token_service.issue_new_family(str(user.id))
        auth = {"Authorization": f"Bearer {access_token}"}

        print(f"\n=== {LABEL} ===")
        results = [
            measure(
                counter,
                "GET /discovery/investors (20)",
                lambda: client.get("/api/v1/discovery/investors?per_page=20"),
                setup=invalidate_discovery_cache,
            ),
            measure(
                counter,
                "GET /portfolios/:id",
                lambda: client.get(f"/api/v1/portfolios/{pid_a}"),
            ),
            measure(
                counter,
                "GET /portfolios/:id/analytics",
                lambda: client.get(f"/api/v1/portfolios/{pid_a}/analytics"),
            ),
            measure(
                counter,
                "GET /portfolios/:id/profile",
                lambda: client.get(f"/api/v1/portfolios/{pid_a}/profile"),
            ),
            measure(
                counter,
                "GET /portfolios/:id/history",
                lambda: client.get(f"/api/v1/portfolios/{pid_a}/history"),
            ),
            measure(
                counter,
                "GET /portfolios/compare",
                lambda: client.get(f"/api/v1/portfolios/compare?ids={pid_a},{pid_b}"),
            ),
            measure(
                counter,
                "GET /users/me/following (100)",
                lambda: client.get("/api/v1/users/me/following?per_page=100", headers=auth),
            ),
        ]

        out = Path(__file__).parent / f"bench-{LABEL}.json"
        out.write_text(json.dumps(results, indent=2))
        print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
