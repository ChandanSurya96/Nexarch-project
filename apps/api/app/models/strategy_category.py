"""StrategyCategory and PortfolioStrategyTag models.

Schema source: docs/database.md — STRATEGY_CATEGORIES and
PORTFOLIO_STRATEGY_TAGS entities.

PortfolioStrategyTag is modeled as its own class (association object), not a
plain SQLAlchemy secondary= table, because it carries an extra column
(tagged_at) beyond the two foreign keys — see docs/database.md "Why
strategy_categories is a join table, not a single strategy column."
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import ForeignKey, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db


class StrategyCategory(db.Model):
    __tablename__ = "strategy_categories"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<StrategyCategory {self.slug!r}>"


class PortfolioStrategyTag(db.Model):
    __tablename__ = "portfolio_strategy_tags"

    portfolio_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("portfolios.id", ondelete="CASCADE"),
        primary_key=True,
    )
    strategy_category_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("strategy_categories.id", ondelete="CASCADE"),
        primary_key=True,
    )
    tagged_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
        nullable=False,
    )

    portfolio: Mapped["Portfolio"] = relationship(  # noqa: F821
        "Portfolio", back_populates="strategy_tags"
    )
    strategy_category: Mapped["StrategyCategory"] = relationship("StrategyCategory")

    def __repr__(self) -> str:
        return f"<PortfolioStrategyTag portfolio={self.portfolio_id} category={self.strategy_category_id}>"
