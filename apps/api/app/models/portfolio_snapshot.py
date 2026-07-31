"""PortfolioSnapshot model.

Schema source: docs/database.md — PORTFOLIO_SNAPSHOTS entity.

Snapshots are the append-only history of a portfolio's computed state at each
sync. They power the "portfolio age," trend charts, and historical health
metrics (diversification, concentration). They are written by the sync worker
(Milestone 2+); the table exists from this migration but starts empty.

See ADR-008: true volatility metrics are deferred to Phase 2+ pending a
market-data vendor decision.

`snapshot_date` is the business date a snapshot represents; it is
deliberately not unique per portfolio — more than one sync can legitimately
land on the same calendar date (e.g. two manual "sync now" calls), and each
gets its own row (ADR-025). `created_at` is what makes "latest" and
chronological ordering deterministic across same-date rows — every query
that wants the most recent snapshot must sort by both, not `snapshot_date`
alone.
"""

import uuid
from datetime import UTC, date, datetime

from sqlalchemy import JSON, Date, ForeignKey, Index, Numeric, Uuid, desc, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db


class PortfolioSnapshot(db.Model):
    __tablename__ = "portfolio_snapshots"
    __table_args__ = (
        # Mirrors the ORDER BY every "latest snapshot" / history query uses,
        # direction included, so the ordering is satisfied from the index
        # rather than a sort step — created_at is the ADR-025 tiebreaker,
        # not decoration. See ADR-035 / migration 0007.
        Index(
            "ix_portfolio_snapshots_portfolio_latest",
            "portfolio_id",
            desc("snapshot_date"),
            desc("created_at"),
        ),
    )

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
    # The deterministic ordering key (ADR-025) — id is a random UUID4, not
    # sequential, so it can't serve as a chronological tiebreaker on its own.
    created_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
        nullable=False,
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    portfolio: Mapped["Portfolio"] = relationship(  # noqa: F821
        "Portfolio", back_populates="snapshots"
    )

    def __repr__(self) -> str:
        return f"<PortfolioSnapshot portfolio={self.portfolio_id} date={self.snapshot_date}>"
