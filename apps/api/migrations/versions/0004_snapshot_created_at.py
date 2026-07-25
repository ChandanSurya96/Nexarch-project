"""Add portfolio_snapshots.created_at — deterministic ordering (ADR-025).

get_latest_snapshot previously ordered by snapshot_date alone, which is not
unique per portfolio (more than one sync can land on the same calendar
date). Without a secondary sort key, which same-date row "wins" as the
latest was undefined. created_at is that key.

Backward compatible: added NOT NULL with server_default=now(), so existing
rows are backfilled to the migration's run time (the closest honest value
available — their true creation time was never tracked) in the same
statement that adds the column, and every row inserted afterward gets its
real creation time automatically.

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-25
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "portfolio_snapshots",
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )


def downgrade() -> None:
    op.drop_column("portfolio_snapshots", "created_at")
