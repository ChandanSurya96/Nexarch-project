"""PublicInvestor model.

Schema source: docs/database.md — PUBLIC_INVESTORS entity.

Every entry must trace to a real, dated, cited public shareholding
disclosure (source_disclosure_url + last_disclosure_update) — never
estimated or inferred (see docs/database.md "Public Investor Example").
"""

import uuid
from datetime import datetime

from sqlalchemy import String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db


class PublicInvestor(db.Model):
    __tablename__ = "public_investors"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    slug: Mapped[str] = mapped_column(String(150), unique=True, nullable=False, index=True)
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_disclosure_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    last_disclosure_update: Mapped[datetime | None] = mapped_column(nullable=True)

    # ── Relationships ─────────────────────────────────────────────────────────
    portfolio: Mapped["Portfolio | None"] = relationship(  # noqa: F821
        "Portfolio", back_populates="public_investor", uselist=False
    )

    def __repr__(self) -> str:
        return f"<PublicInvestor {self.slug!r}>"
