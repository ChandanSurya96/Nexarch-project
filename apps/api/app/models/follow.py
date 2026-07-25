"""Follow model.

Schema source: docs/database.md — FOLLOWS entity.

Following never moves money or places an order (see
docs/product-requirements.md "Feature: Following") — this table exists
purely to power "portfolios I follow" / "am I following this" lookups.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import ForeignKey, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db


class Follow(db.Model):
    __tablename__ = "follows"
    __table_args__ = (
        # Prevents duplicate follows and doubles as the fast "am I
        # following this" existence check, per docs/database.md.
        UniqueConstraint(
            "follower_user_id", "followed_portfolio_id", name="uq_follows_follower_portfolio"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    follower_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    followed_portfolio_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("portfolios.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
        nullable=False,
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    follower: Mapped["User"] = relationship("User")  # noqa: F821
    followed_portfolio: Mapped["Portfolio"] = relationship("Portfolio")  # noqa: F821

    def __repr__(self) -> str:
        return f"<Follow follower={self.follower_user_id} portfolio={self.followed_portfolio_id}>"
