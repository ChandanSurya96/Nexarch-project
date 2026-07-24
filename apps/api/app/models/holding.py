"""Holding model.

Schema source: docs/database.md — HOLDINGS entity.

Holdings are point-in-time (overwritten on each sync), not a running ledger.
Historical changes are captured in PortfolioSnapshot instead.
See docs/database.md "Design Notes" for why.
"""

import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, Numeric, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db


class Holding(db.Model):
    __tablename__ = "holdings"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    portfolio_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("portfolios.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    # ISIN is the most reliable cross-source join key (see docs/broker-integrations.md).
    isin: Mapped[str | None] = mapped_column(String(12), nullable=True)
    exchange: Mapped[str | None] = mapped_column(String(10), nullable=True)  # "NSE" | "BSE"
    quantity: Mapped[float] = mapped_column(Numeric(18, 6), nullable=False)
    avg_cost_price: Mapped[float | None] = mapped_column(Numeric(18, 6), nullable=True)
    # sector is enriched from a sector-mapping reference, not sourced directly
    # from brokers (brokers don't reliably expose this — see broker-integrations.md).
    sector: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    market_cap_category: Mapped[str | None] = mapped_column(
        String(10), nullable=True
    )  # "large" | "mid" | "small"
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False)

    # ── Relationships ─────────────────────────────────────────────────────────
    portfolio: Mapped["Portfolio"] = relationship(  # noqa: F821
        "Portfolio", back_populates="holdings"
    )

    def __repr__(self) -> str:
        return f"<Holding {self.symbol!r} qty={self.quantity}>"
