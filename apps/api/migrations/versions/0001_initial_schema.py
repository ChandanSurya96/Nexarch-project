"""Initial schema — Phase 1 Milestone 1.

Creates the five tables in scope for this milestone:
    users, broker_connections, portfolios, holdings, portfolio_snapshots

Tables explicitly deferred to later milestones (not created here):
    strategy_categories, portfolio_strategy_tags — no writer until Milestone 2
    public_investors       — Public Investor Library, Milestone 2+
    follows, audit_logs    — Milestone 2+

All indexes from docs/database.md for these five tables are included.

See docs/database.md for schema rationale and docs/decisions.md for ADRs
referenced inline (ADR-004, ADR-006, ADR-011).

Revision ID: 0001
Revises: None (this is the initial migration)
Create Date: 2026-07-21
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Enums ─────────────────────────────────────────────────────────────────
    # Create enums explicitly so they can be referenced in multiple tables
    # and dropped cleanly in downgrade().
    connection_method_enum = postgresql.ENUM(
        "broker_api",
        "account_aggregator",
        name="connection_method_enum",
        create_type=False,
    )
    broker_connection_status_enum = postgresql.ENUM(
        "active",
        "expired",
        "revoked",
        "error",
        name="broker_connection_status_enum",
        create_type=False,
    )
    portfolio_type_enum = postgresql.ENUM(
        "verified",
        "public",
        name="portfolio_type_enum",
        create_type=False,
    )

    connection_method_enum.create(op.get_bind(), checkfirst=True)
    broker_connection_status_enum.create(op.get_bind(), checkfirst=True)
    portfolio_type_enum.create(op.get_bind(), checkfirst=True)

    # ── 1. users ──────────────────────────────────────────────────────────────
    # Indexed: unique(email), unique(username) per docs/database.md
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(254), nullable=False),
        sa.Column("username", sa.String(50), nullable=False),
        sa.Column("password_hash", sa.String(128), nullable=False),
        sa.Column("display_name", sa.String(100), nullable=True),
        sa.Column("bio", sa.Text, nullable=True),
        sa.Column("avatar_url", sa.String(2048), nullable=True),
        sa.Column("is_public", sa.Boolean, nullable=False, server_default="false"),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_username", "users", ["username"], unique=True)

    # ── 2. broker_connections ─────────────────────────────────────────────────
    # Indexed: (user_id) per docs/database.md
    op.create_table(
        "broker_connections",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("broker_name", sa.String(50), nullable=False),
        sa.Column(
            "connection_method",
            postgresql.ENUM(
                "broker_api", "account_aggregator", name="connection_method_enum", create_type=False
            ),
            nullable=False,
            server_default="broker_api",
        ),
        # Tokens encrypted at rest before storage (see docs/security.md).
        sa.Column("access_token_encrypted", sa.Text, nullable=True),
        sa.Column("refresh_token_encrypted", sa.Text, nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM(
                "active", "expired", "revoked", "error",
                name="broker_connection_status_enum",
                create_type=False,
            ),
            nullable=False,
            server_default="active",
        ),
        sa.Column(
            "connected_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("last_synced_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("token_expires_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.create_index("ix_broker_connections_user_id", "broker_connections", ["user_id"])

    # ── 3. portfolios ─────────────────────────────────────────────────────────
    # Indexed: (user_id), (is_public) per docs/database.md
    # public_investor_id index deferred — public_investors table not in scope yet.
    op.create_table(
        "portfolios",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        # Nullable per ADR-006 — NULL for public-investor portfolios.
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=True,
        ),
        # public_investor_id FK added in a later migration when that table exists.
        sa.Column("public_investor_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "broker_connection_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("broker_connections.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "portfolio_type",
            postgresql.ENUM("verified", "public", name="portfolio_type_enum", create_type=False),
            nullable=False,
            server_default="verified",
        ),
        # is_public defaults to False — opt-in only per ADR-011.
        sa.Column("is_public", sa.Boolean, nullable=False, server_default="false"),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        # Check constraint enforcing the nullable-owner invariant (ADR-006):
        # exactly one of user_id / public_investor_id is set, never both, never neither.
        sa.CheckConstraint(
            "(portfolio_type = 'verified' AND user_id IS NOT NULL AND public_investor_id IS NULL)"
            " OR "
            "(portfolio_type = 'public' AND user_id IS NULL AND public_investor_id IS NOT NULL)",
            name="ck_portfolio_owner_invariant",
        ),
    )
    op.create_index("ix_portfolios_user_id", "portfolios", ["user_id"])
    op.create_index("ix_portfolios_is_public", "portfolios", ["is_public"])

    # ── 4. holdings ───────────────────────────────────────────────────────────
    # Indexed: (portfolio_id), (sector) per docs/database.md
    op.create_table(
        "holdings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "portfolio_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("portfolios.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("symbol", sa.String(20), nullable=False),
        # ISIN is the most reliable cross-source join key (broker-integrations.md).
        sa.Column("isin", sa.String(12), nullable=True),
        sa.Column("exchange", sa.String(10), nullable=True),
        sa.Column("quantity", sa.Numeric(18, 6), nullable=False),
        sa.Column("avg_cost_price", sa.Numeric(18, 6), nullable=True),
        # sector enriched from sector-mapping reference (not from broker directly).
        sa.Column("sector", sa.String(100), nullable=True),
        sa.Column("market_cap_category", sa.String(10), nullable=True),
        sa.Column("as_of_date", sa.Date, nullable=False),
    )
    op.create_index("ix_holdings_portfolio_id", "holdings", ["portfolio_id"])
    op.create_index("ix_holdings_sector", "holdings", ["sector"])

    # ── 5. portfolio_snapshots ────────────────────────────────────────────────
    # Indexed: composite (portfolio_id, snapshot_date) per docs/database.md
    op.create_table(
        "portfolio_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "portfolio_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("portfolios.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("snapshot_date", sa.Date, nullable=False),
        sa.Column("total_value", sa.Numeric(20, 6), nullable=True),
        # JSONB used for flexible metric shapes; health_metrics extensible for
        # Phase 2 volatility fields without a new migration (ADR-008).
        sa.Column("sector_allocation", postgresql.JSONB, nullable=True),
        sa.Column("asset_allocation", postgresql.JSONB, nullable=True),
        sa.Column("health_metrics", postgresql.JSONB, nullable=True),
    )
    op.create_index(
        "ix_portfolio_snapshots_portfolio_date",
        "portfolio_snapshots",
        ["portfolio_id", "snapshot_date"],
    )


def downgrade() -> None:
    op.drop_table("portfolio_snapshots")
    op.drop_table("holdings")
    op.drop_table("portfolios")
    op.drop_table("broker_connections")
    op.drop_table("users")

    # Drop enums after tables that reference them are gone.
    op.execute("DROP TYPE IF EXISTS portfolio_type_enum")
    op.execute("DROP TYPE IF EXISTS broker_connection_status_enum")
    op.execute("DROP TYPE IF EXISTS connection_method_enum")
