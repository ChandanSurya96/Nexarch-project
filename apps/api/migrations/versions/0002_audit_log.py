"""Add audit_logs table — Phase 1 Milestone 2.

Creates the audit_logs table deferred from migration 0001. Needed now because
Milestone 2 introduces broker connect/disconnect/sync/error events, and
docs/security.md requires all of those (plus login/token_refresh, retrofitted
onto Milestone 1's auth endpoints in this same milestone) to be logged here.

See docs/database.md for schema rationale.

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-25
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    audit_event_type_enum = postgresql.ENUM(
        "connect",
        "disconnect",
        "sync",
        "login",
        "token_refresh",
        "error",
        name="audit_event_type_enum",
        create_type=False,
    )
    audit_event_type_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "event_type",
            postgresql.ENUM(
                "connect", "disconnect", "sync", "login", "token_refresh", "error",
                name="audit_event_type_enum",
                create_type=False,
            ),
            nullable=False,
        ),
        # Column is named "metadata" in the DB; the ORM model maps it to the
        # Python attribute `event_metadata` since `metadata` is reserved on
        # SQLAlchemy declarative models.
        sa.Column("metadata", postgresql.JSONB, nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    # Composite (user_id, created_at) per docs/database.md — also serves
    # user_id-only lookups via the leftmost-prefix rule, so no separate
    # single-column index is needed.
    op.create_index("ix_audit_logs_user_id_created_at", "audit_logs", ["user_id", "created_at"])


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.execute("DROP TYPE IF EXISTS audit_event_type_enum")
