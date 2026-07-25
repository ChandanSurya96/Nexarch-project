"""Discovery, Public Investor Library, and Follows — Phase 1 Milestone 3.

Creates the tables deferred since migration 0001:
    strategy_categories, portfolio_strategy_tags, public_investors, follows

Also finally adds the FK constraint + index on portfolios.public_investor_id,
deferred since migration 0001 because public_investors didn't exist yet
(see docs/database.md and app/models/portfolio.py).

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-25
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── strategy_categories ───────────────────────────────────────────────────
    op.create_table(
        "strategy_categories",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
    )
    op.create_index("ix_strategy_categories_name", "strategy_categories", ["name"], unique=True)
    op.create_index("ix_strategy_categories_slug", "strategy_categories", ["slug"], unique=True)

    # ── public_investors ──────────────────────────────────────────────────────
    op.create_table(
        "public_investors",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("slug", sa.String(150), nullable=False),
        sa.Column("bio", sa.Text, nullable=True),
        sa.Column("source_disclosure_url", sa.String(2048), nullable=True),
        sa.Column("last_disclosure_update", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.create_index("ix_public_investors_slug", "public_investors", ["slug"], unique=True)

    # ── portfolio_strategy_tags (association object, composite PK) ───────────
    # Indexed: composite (portfolio_id, strategy_category_id) per docs/database.md
    op.create_table(
        "portfolio_strategy_tags",
        sa.Column(
            "portfolio_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("portfolios.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "strategy_category_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("strategy_categories.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "tagged_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # ── follows ────────────────────────────────────────────────────────────────
    # Indexed: unique(follower_user_id, followed_portfolio_id) per docs/database.md
    op.create_table(
        "follows",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "follower_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "followed_portfolio_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("portfolios.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_unique_constraint(
        "uq_follows_follower_portfolio", "follows", ["follower_user_id", "followed_portfolio_id"]
    )

    # ── portfolios.public_investor_id — FK + index deferred since 0001 ───────
    op.create_foreign_key(
        "fk_portfolios_public_investor",
        "portfolios",
        "public_investors",
        ["public_investor_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_portfolios_public_investor_id", "portfolios", ["public_investor_id"])


def downgrade() -> None:
    op.drop_index("ix_portfolios_public_investor_id", table_name="portfolios")
    op.drop_constraint("fk_portfolios_public_investor", "portfolios", type_="foreignkey")

    op.drop_table("follows")
    op.drop_table("portfolio_strategy_tags")
    op.drop_table("public_investors")
    op.drop_table("strategy_categories")
