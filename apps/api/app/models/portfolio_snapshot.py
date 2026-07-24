"""PortfolioSnapshot model.

Schema source: docs/database.md — PORTFOLIO_SNAPSHOTS entity.

Snapshots are the append-only history of a portfolio's computed state at each
sync. They power the "portfolio age," trend charts, and historical health
metrics (diversification, concentration). They are written by the sync worker
(Milestone 2+); the table exists from this migration but starts empty.

See ADR-008: true volatility metrics are deferred to Phase 2+ pending a
market-data vendor decision.
"""

import uuid
from datetime import date

from sqlalchemy import JSON, Date, ForeignKey, Numeric, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db


class PortfolioSnapshot(db.Model):
    __tablename__ = "portfolio_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    portfolio_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("portfolios.id", ondelete="CASCADE"),
        nullable=False,
    )
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)
    total_value: Mapped[float | None] = mapped_column(Numeric(20, 6), nullable=True)
    # sa.JSON works on both SQLite (tests) and Postgres (production as JSONB via migration).
    # Shape is intentionally flexible so Phase 2 can add volatility fields
    # without a new migration (ADR-008).
    sector_allocation: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    asset_allocation: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    health_metrics: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # ── Relationships ─────────────────────────────────────────────────────────
    portfolio: Mapped["Portfolio"] = relationship(  # noqa: F821
        "Portfolio", back_populates="snapshots"
    )

    def __repr__(self) -> str:
        return f"<PortfolioSnapshot portfolio={self.portfolio_id} date={self.snapshot_date}>"
