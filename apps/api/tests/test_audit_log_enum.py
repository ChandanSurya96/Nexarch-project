"""Guard against audit event types that no migration ever defined.

This exact bug has shipped twice — 'logout'/'refresh_reuse_detected' (fixed
by migration 0006) and 'reconnect' (fixed by 0008, after living undetected
in the reconnect path since Milestone 2). Both had the same shape: a service
passes a new string to audit_service.log_event(), nobody adds it to the
Postgres ENUM, and every test still passes because SQLite treats an ENUM
column as free text. In production the insert fails with
psycopg2.errors.InvalidTextRepresentation and the request 500s.

CI now runs the suite against real Postgres, which closes the gap for any
path a test actually exercises. This file closes the rest of it: it reads
the source, so it fails on *any* unmigrated event type — including ones no
test touches — and it fails on SQLite, locally, in under a second.
"""

import ast
import re
from pathlib import Path

import pytest

from app.models.audit_log import AuditLog

APP_DIR = Path(__file__).resolve().parent.parent / "app"
MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations" / "versions"


def _emitted_event_types() -> dict[str, str]:
    """Every string literal passed as log_event's event_type, by source location."""
    found: dict[str, str] = {}

    for path in APP_DIR.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if not (isinstance(func, ast.Attribute) and func.attr == "log_event"):
                continue
            if len(node.args) < 2:
                continue

            arg = node.args[1]
            # Covers both the plain-literal call sites and the conditional
            # one in broker_connection_service ("connect" if is_new else
            # "reconnect") — the ternary is precisely how 'reconnect' hid.
            candidates = [arg.body, arg.orelse] if isinstance(arg, ast.IfExp) else [arg]

            for candidate in candidates:
                if isinstance(candidate, ast.Constant) and isinstance(candidate.value, str):
                    where = f"{path.relative_to(APP_DIR.parent)}:{candidate.lineno}"
                    found.setdefault(candidate.value, where)

    return found


def _migrated_event_types() -> set[str]:
    """Enum values as the migrations actually define them."""
    values: set[str] = set()

    for path in sorted(MIGRATIONS_DIR.glob("*.py")):
        source = path.read_text(encoding="utf-8")

        # 0002 creates the type via postgresql.ENUM("connect", "disconnect", ...)
        created = re.search(
            r"audit_event_type_enum\s*=\s*postgresql\.ENUM\((.*?)name=",
            source,
            re.DOTALL,
        )
        if created:
            values.update(re.findall(r'"([a-z_]+)"', created.group(1)))

        # Later migrations extend it one ALTER TYPE at a time.
        values.update(
            re.findall(
                r"ALTER TYPE audit_event_type_enum ADD VALUE(?: IF NOT EXISTS)? '([a-z_]+)'",
                source,
            )
        )

    return values


class TestAuditEventTypeEnum:
    def test_migrations_define_the_expected_baseline(self):
        """Sanity-check the parsers before trusting what they compare."""
        migrated = _migrated_event_types()
        assert "connect" in migrated, "parser found no enum values — the regex has drifted"
        assert "reconnect" in migrated, "migration 0008 should define 'reconnect'"

        emitted = _emitted_event_types()
        assert "reconnect" in emitted, (
            "no call site emits 'reconnect' — if that path was intentionally "
            "removed, drop it from AuditLog.EVENT_TYPES too"
        )

    def test_every_emitted_event_type_is_migrated(self):
        """The regression proper. Fails against the pre-0008 migration set."""
        emitted = _emitted_event_types()
        migrated = _migrated_event_types()

        undefined = {value: where for value, where in emitted.items() if value not in migrated}

        assert not undefined, (
            "These audit event types are written by app code but no migration "
            "defines them in audit_event_type_enum. On Postgres each one is a "
            "guaranteed 500 (InvalidTextRepresentation); SQLite accepts them "
            "silently, which is why this check reads the source instead of "
            f"inserting a row: {undefined}"
        )

    def test_model_event_types_match_the_migrations(self):
        """AuditLog.EVENT_TYPES is documentation — keep it honest."""
        assert set(AuditLog.EVENT_TYPES) == _migrated_event_types()

    @pytest.mark.parametrize("event_type", sorted(AuditLog.EVENT_TYPES))
    def test_event_type_fits_the_column(self, event_type):
        """String(30) — 'refresh_reuse_detected' is already 22 characters."""
        assert len(event_type) <= 30
