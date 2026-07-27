"""Unique constraint on broker_connections.user_id — Phase 2.5 hardening (ADR-033).

At most one broker connection per user, period. disconnect() fully deletes
a row rather than soft-deleting it (see broker_connection_service.py), so
this invariant is "0 or 1 rows for a given user_id" — a plain unique
constraint enforces it at the database layer, converting the still-open
TOCTOU race in the app-level guard (ADR-030) into a clean IntegrityError
instead of silent duplicate rows.

PRE-DEPLOY CHECK (no production database exists yet, so this is a note for
whenever one does): before running this migration against a database with
real data, verify there are no existing duplicate user_id rows:
    SELECT user_id, COUNT(*) FROM broker_connections GROUP BY user_id HAVING COUNT(*) > 1;
If that returns any rows, this migration will fail outright — resolve the
duplicates first (keep the row with a linked portfolio_id, or the most
recently connected_at, per docs/decisions.md ADR-033).

Revision ID: 0005
Revises: 0004
Create Date: 2026-07-26
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index("ix_broker_connections_user_id", table_name="broker_connections")
    op.create_unique_constraint(
        "uq_broker_connections_user_id", "broker_connections", ["user_id"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_broker_connections_user_id", "broker_connections", type_="unique")
    op.create_index("ix_broker_connections_user_id", "broker_connections", ["user_id"])
