"""Performance indexes — Phase 2.5 Slice 3 (ADR-035).

Three index changes, each justified by a specific measured query. No
speculative indexing: every change below traces to a query that exists in
the codebase today.

1. ADD ix_portfolio_strategy_tags_category on (strategy_category_id).
   `GET /discovery/investors?strategy=<slug>` resolves the slug to a
   strategy_category_id, then finds every tag row with that id
   (discovery_service.list_investors' join). The table's only existing
   index is its composite PK (portfolio_id, strategy_category_id) — with
   strategy_category_id as the *trailing* column, so it can't serve a
   lookup keyed on that column alone. This adds the missing access path.

2. REPLACE ix_portfolio_snapshots_portfolio_date
      (portfolio_id, snapshot_date)
   with (portfolio_id, snapshot_date DESC, created_at DESC).
   Every "latest snapshot" query orders by BOTH snapshot_date and
   created_at — created_at is the ADR-025 tiebreaker that makes "latest"
   deterministic when two syncs land on the same calendar date. The old
   index stopped at snapshot_date, leaving a sort step for the tiebreaker.
   Matching the index to the actual ORDER BY (including direction) lets
   the planner satisfy the ordering from the index alone.

3. DROP ix_holdings_sector.
   Verified unused before dropping: no query anywhere in app/ filters,
   orders, or groups by holdings.sector. Sector allocation is computed in
   Python from already-loaded Holding rows
   (analytics_service.compute_sector_allocation), never in SQL. The index
   was therefore pure write overhead — and specifically bad here, because
   sync_service deletes and reinserts *every* holding on *every* sync
   (docs/database.md's point-in-time holdings model), so this index was
   being rebuilt continuously to serve zero reads.

Production note: these use plain CREATE INDEX, which takes a write lock
for the duration. No production deployment exists yet, and the tables are
small, so that's fine now. If this is ever applied to a large live table,
switch to CREATE INDEX CONCURRENTLY — which cannot run inside Alembic's
transaction, so it needs its own migration with
`op.get_context().autocommit_block()`.

Revision ID: 0007
Revises: 0006
Create Date: 2026-07-27
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_portfolio_strategy_tags_category",
        "portfolio_strategy_tags",
        ["strategy_category_id"],
    )

    op.drop_index("ix_portfolio_snapshots_portfolio_date", table_name="portfolio_snapshots")
    op.execute(
        "CREATE INDEX ix_portfolio_snapshots_portfolio_latest "
        "ON portfolio_snapshots (portfolio_id, snapshot_date DESC, created_at DESC)"
    )

    op.drop_index("ix_holdings_sector", table_name="holdings")


def downgrade() -> None:
    op.create_index("ix_holdings_sector", "holdings", ["sector"])

    op.drop_index("ix_portfolio_snapshots_portfolio_latest", table_name="portfolio_snapshots")
    op.create_index(
        "ix_portfolio_snapshots_portfolio_date",
        "portfolio_snapshots",
        ["portfolio_id", "snapshot_date"],
    )

    op.drop_index("ix_portfolio_strategy_tags_category", table_name="portfolio_strategy_tags")
