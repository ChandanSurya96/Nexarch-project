"""AuditLog model.

Schema source: docs/database.md — AUDIT_LOGS entity.

Every connect/disconnect/sync/error/login/token_refresh event is written here
(see docs/security.md "Incident Response Basics"). Written by services, never
by routes directly, so logging can't be accidentally skipped on one code path.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import JSON, ForeignKey, Index, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db


class AuditLog(db.Model):
    __tablename__ = "audit_logs"
    __table_args__ = (
        # Composite (user_id, created_at) only, per docs/database.md — this
        # also serves user_id-only lookups via the leftmost-prefix rule, so
        # no separate single-column index is created.
        Index("ix_audit_logs_user_id_created_at", "user_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    # "connect" | "disconnect" | "sync" | "login" | "token_refresh" | "error"
    event_type: Mapped[str] = mapped_column(String(30), nullable=False)
    # sa.JSON works on both SQLite (tests) and Postgres (production as JSONB).
    # Never store token values or password material here (see docs/security.md).
    event_metadata: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
        nullable=False,
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    user: Mapped["User"] = relationship("User")  # noqa: F821

    def __repr__(self) -> str:
        return f"<AuditLog {self.event_type!r} user={self.user_id}>"
