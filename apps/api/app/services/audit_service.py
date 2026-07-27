"""Audit logging — shared by auth and broker-connection services.

A single write path so every event type in docs/database.md's AUDIT_LOGS enum
(connect, disconnect, sync, login, logout, token_refresh, refresh_reuse_detected,
error) goes through the same function, rather than each service building its
own AuditLog row. See docs/security.md "Incident Response Basics".

`refresh_reuse_detected` (ADR-030) is worth alerting on specifically — a
spike in this event, unlike routine session expiry, is a real theft signal.
"""

from __future__ import annotations

import uuid

from app.extensions import db
from app.models.audit_log import AuditLog


def log_event(user_id: uuid.UUID | str, event_type: str, metadata: dict | None = None) -> None:
    """Write an audit_logs row.

    Args:
        user_id: The user the event pertains to.
        event_type: One of connect | disconnect | sync | login | logout |
            token_refresh | refresh_reuse_detected | error.
        metadata: Arbitrary JSON-serializable context. Never include token values,
            password material, or other secrets here (see docs/security.md).
    """
    entry = AuditLog(
        user_id=uuid.UUID(str(user_id)),
        event_type=event_type,
        event_metadata=metadata or {},
    )
    db.session.add(entry)
    db.session.commit()
