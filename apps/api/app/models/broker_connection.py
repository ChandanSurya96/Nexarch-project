"""BrokerConnection model.

Schema source: docs/database.md — BROKER_CONNECTIONS entity.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import ForeignKey, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db


class BrokerConnection(db.Model):
    __tablename__ = "broker_connections"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # unique, not just indexed (ADR-033): at most one broker connection per
    # user, period — disconnect() fully deletes a row rather than soft-
    # deleting it, so the true invariant is "0 or 1 rows for this user_id."
    # Backstops the app-level check in broker_connection_service.py, whose
    # own check-then-act guard (ADR-030) has a real, acknowledged TOCTOU
    # race under concurrent requests.
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    broker_name: Mapped[str] = mapped_column(String(50), nullable=False)
    # "broker_api" | "account_aggregator" — stored as a plain string so the model
    # works on both SQLite (tests) and Postgres (production). The migration file
    # uses postgresql.ENUM for the actual DB column type.
    connection_method: Mapped[str] = mapped_column(String(30), nullable=False, default="broker_api")
    # Tokens are encrypted at rest before being stored (see docs/security.md).
    # The encryption/decryption step happens in the service layer, not here.
    access_token_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    refresh_token_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    # "active" | "expired" | "revoked" | "error"
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    connected_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
        nullable=False,
    )
    last_synced_at: Mapped[datetime | None] = mapped_column(nullable=True)
    token_expires_at: Mapped[datetime | None] = mapped_column(nullable=True)

    # ── Relationships ─────────────────────────────────────────────────────────
    user: Mapped["User"] = relationship("User", back_populates="broker_connections")  # noqa: F821
    portfolio: Mapped["Portfolio | None"] = relationship(  # noqa: F821
        "Portfolio", back_populates="broker_connection", uselist=False
    )

    def __repr__(self) -> str:
        return f"<BrokerConnection {self.broker_name!r} user={self.user_id}>"
