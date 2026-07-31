"""Add 'reconnect' to audit_event_type_enum.

A latent production bug, not a test artifact. `broker_connection_service`
has emitted "reconnect" since Milestone 2 — it's the event written whenever
a user re-authorises an existing broker connection rather than creating a
new one:

    audit_service.log_event(user_id, "connect" if is_new else "reconnect", ...)

but `audit_event_type_enum` has never accepted that value: migration 0002
defined six values without it, and 0006 added only 'logout' and
'refresh_reuse_detected'. Against real Postgres, reconnecting therefore
fails with psycopg2.errors.InvalidTextRepresentation, leaving the session
in a PendingRollbackError state and returning a 500 — *after* the
connection row itself has already been committed, so the reconnect
silently succeeds while the user sees an error.

This is on the routine path, not an edge case: Kite-style daily token
expiry means reconnecting is something an active user does often.

Why it survived three hardening slices: the test suite runs on SQLite,
which does not enforce Postgres ENUM types, and no prior CI ran the suite
against Postgres. Slice 4's CI does — and caught it on its first real run.
`docs/database.md` had documented 'reconnect' as a valid value all along,
so the docs described the intended behaviour and the schema didn't
implement it. Same failure mode as 0006, one slice apart, which is why the
fix this time was preceded by auditing *every* log_event call site in
app/ against the enum rather than only the value that happened to fail.

Revision ID: 0008
Revises: 0007
Create Date: 2026-07-31
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Safe as the only statement in its own transaction (Postgres 12+); the
    # new value must not be *used* in the same transaction that adds it.
    op.execute("ALTER TYPE audit_event_type_enum ADD VALUE IF NOT EXISTS 'reconnect'")


def downgrade() -> None:
    # Same reasoning as 0006: Postgres has no "remove enum value", only a
    # full type rebuild (create replacement type, cast the column, drop,
    # rename). Not implemented — no production deployment exists, so this
    # would never run against real data, and 'reconnect' rows are audit
    # history that shouldn't be deleted casually to satisfy a downgrade.
    raise NotImplementedError(
        "Downgrading past 0008 requires manually rebuilding audit_event_type_enum "
        "(see this function's comment) — not implemented, no production data exists yet."
    )
