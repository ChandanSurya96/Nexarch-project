"""AuditLog model.

Schema source: docs/database.md — AUDIT_LOGS entity.

Every connect/reconnect/disconnect/sync/error/login/logout/token_refresh/
refresh_reuse_detected event is written here (see docs/security.md
"Incident Response Basics"). Written by services, never by routes directly,
so logging can't be accidentally skipped on one code path. event_type is a
plain string here but a real Postgres ENUM at the DB layer (migrations
0002/0006/0008) — adding a new event type needs both a new migration value
and, in dev/CI, actually running `flask db upgrade` before it's usable, or
inserts fail with psycopg2.errors.InvalidTextRepresentation.

This has now bitten twice (0006, 0008) because SQLite — the test suite's
database — silently accepts any string for an ENUM column, so a missing
value passes every local test and only fails against real Postgres. CI now
runs the suite against Postgres specifically so that gap closes, and
tests/test_audit_log_enum.py asserts this list matches the migrations.
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
    # Keep in sync with audit_event_type_enum (migrations 0002/0006/0008) —
    # tests/test_audit_log_enum.py fails if these drift apart.
    EVENT_TYPES = (
        "connect",
        "reconnect",
        "disconnect",
        "sync",
        "login",
        "logout",
        "token_refresh",
        "refresh_reuse_detected",
        "error",
    )

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
