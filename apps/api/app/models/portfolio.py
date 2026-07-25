"""Portfolio model.

Schema source: docs/database.md — PORTFOLIOS entity.

Design note (ADR-006): a single portfolios table with two nullable owner FKs
(user_id / public_investor_id) rather than separate verified/public tables.
A check constraint enforces the invariant that exactly one FK is set, never
both and never neither.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db


class Portfolio(db.Model):
    __tablename__ = "portfolios"
    __table_args__ = (
        # Invariant from ADR-006 and database.md:
        # - verified portfolio  → user_id set,             public_investor_id NULL
        # - public portfolio    → user_id NULL,             public_investor_id set
        CheckConstraint(
            "(portfolio_type = 'verified' AND user_id IS NOT NULL AND public_investor_id IS NULL)"
            " OR "
            "(portfolio_type = 'public' AND user_id IS NULL AND public_investor_id IS NOT NULL)",
            name="ck_portfolio_owner_invariant",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Nullable — NULL for public-investor portfolios (see ADR-006).
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    # Nullable — NULL for user portfolios.
    public_investor_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("public_investors.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    broker_connection_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("broker_connections.id", ondelete="SET NULL"),
        nullable=True,
    )
    # "verified" | "public" — stored as a plain string for cross-DB compat.
    portfolio_type: Mapped[str] = mapped_column(String(20), nullable=False, default="verified")
    is_public: Mapped[bool] = mapped_column(
        Boolean,
        default=False,  # opt-in only — see ADR-011
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    user: Mapped["User | None"] = relationship(  # noqa: F821
        "User",
        back_populates="portfolios",
        foreign_keys=[user_id],
    )
    broker_connection: Mapped["BrokerConnection | None"] = relationship(  # noqa: F821
        "BrokerConnection", back_populates="portfolio"
    )
    holdings: Mapped[list["Holding"]] = relationship(  # noqa: F821
        "Holding", back_populates="portfolio", cascade="all, delete-orphan"
    )
    snapshots: Mapped[list["PortfolioSnapshot"]] = relationship(  # noqa: F821
        "PortfolioSnapshot", back_populates="portfolio", cascade="all, delete-orphan"
    )
    public_investor: Mapped["PublicInvestor | None"] = relationship(  # noqa: F821
        "PublicInvestor", back_populates="portfolio"
    )
    strategy_tags: Mapped[list["PortfolioStrategyTag"]] = relationship(  # noqa: F821
        "PortfolioStrategyTag", back_populates="portfolio", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Portfolio {self.id} type={self.portfolio_type!r}>"
