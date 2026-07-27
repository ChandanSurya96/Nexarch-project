"""Add 'logout' and 'refresh_reuse_detected' to audit_event_type_enum.

Phase 2.5 hardening (ADR-029/030) added real audit logging for these two
event types — POST /auth/logout now revokes the refresh-token family
server-side, and refresh-token reuse detection needed its own event so a
spike in it can be alerted on distinctly from routine expiry. Both were
already being passed to audit_service.log_event(), but the Postgres enum
backing audit_logs.event_type was never updated to accept them: SQLite
(the test suite's database) doesn't enforce this the way Postgres's
migration-defined ENUM type does, so the gap only surfaced when logging a
real refresh-reuse event against a real Postgres database
(psycopg2.errors.InvalidTextRepresentation).

Revision ID: 0006
Revises: 0005
Create Date: 2026-07-26
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ALTER TYPE ... ADD VALUE cannot run in the same transaction as a
    # statement that uses the new value, but it's fine as the only
    # statement in this migration's own transaction (Postgres 12+).
    op.execute("ALTER TYPE audit_event_type_enum ADD VALUE IF NOT EXISTS 'logout'")
    op.execute("ALTER TYPE audit_event_type_enum ADD VALUE IF NOT EXISTS 'refresh_reuse_detected'")


def downgrade() -> None:
    # Postgres has no direct "remove enum value" operation — the only real
    # way is to rebuild the type (create a new one without the value, cast
    # every existing row's column to it, drop the old type, rename). Not
    # implemented here: no production deployment exists yet, so there is no
    # real data this would ever need to run against, and adding the ceremony
    # for a downgrade path that will never be exercised isn't worth it. If a
    # downgrade past this revision is ever genuinely needed, first confirm
    # no 'logout'/'refresh_reuse_detected' rows exist (they're harmless
    # audit history, not something to delete casually), then do the
    # create-new-type/swap dance by hand.
    raise NotImplementedError(
        "Downgrading past 0006 requires manually rebuilding audit_event_type_enum "
        "(see this function's docstring) — not implemented, no production data exists yet."
    )
