"""Portfolio activity — descriptive diff over snapshot history (ADR-015).

Inspired by, but deliberately not copying, copy-trading apps' rebalance
feeds (see the system-design exploration earlier in this project's history).
Nexarch has no transaction-level data — holdings are point-in-time per
docs/database.md — so "activity" here is strictly a description of what
changed between two consecutive syncs, never a cause, a recommendation, or
"auto-copy" language. No new table: computed on read from
portfolio_snapshots, which Milestone 2's sync worker already writes.
"""

from __future__ import annotations

import uuid
from datetime import date

from app.models.portfolio_snapshot import PortfolioSnapshot
from app.schemas.portfolio import ActivityEntrySchema

# Ignore sector-weight moves smaller than this — noise, not a real shift.
_MIN_MEANINGFUL_SECTOR_CHANGE = 0.01
# Cap how many sector changes go into the generated sentence, so it stays readable.
_MAX_SECTORS_IN_SUMMARY = 3

_entry_schema = ActivityEntrySchema()


def get_activity(portfolio_id: uuid.UUID) -> list[dict]:
    """Most-recent-first list of diffs between consecutive snapshots.
    Empty list if there are fewer than 2 snapshots yet."""
    snapshots = (
        PortfolioSnapshot.query.filter_by(portfolio_id=portfolio_id)
        .order_by(PortfolioSnapshot.snapshot_date.asc())
        .all()
    )
    if len(snapshots) < 2:
        return []

    entries = [
        entry
        # strict=False: snapshots[1:] is deliberately one shorter, since this
        # zips each snapshot with the one right after it.
        for prev, curr in zip(snapshots, snapshots[1:], strict=False)
        if (entry := _diff(prev, curr)) is not None
    ]
    entries.reverse()
    return _entry_schema.dump(entries, many=True)


def _sector_changes(prev: PortfolioSnapshot, curr: PortfolioSnapshot) -> list[dict]:
    prev_alloc = prev.sector_allocation or {}
    curr_alloc = curr.sector_allocation or {}
    changes = []
    for sector in sorted(set(prev_alloc) | set(curr_alloc)):
        before = prev_alloc.get(sector, 0.0)
        after = curr_alloc.get(sector, 0.0)
        if abs(after - before) >= _MIN_MEANINGFUL_SECTOR_CHANGE:
            changes.append({"sector": sector, "before": before, "after": after})
    return changes


def _holding_count_change(prev: PortfolioSnapshot, curr: PortfolioSnapshot) -> dict | None:
    prev_count = (prev.health_metrics or {}).get("holding_count")
    curr_count = (curr.health_metrics or {}).get("holding_count")
    if prev_count is None or curr_count is None or prev_count == curr_count:
        return None
    return {"before": prev_count, "after": curr_count}


def _summary(
    from_date: date, to_date: date, sector_changes: list[dict], holding_count_change: dict | None
) -> str:
    sentence = f"Between {from_date.isoformat()} and {to_date.isoformat()}"
    parts = []
    if sector_changes:
        shown = sector_changes[:_MAX_SECTORS_IN_SUMMARY]
        formatted = [
            f"{c['sector']} {round(c['before'] * 100)}%→{round(c['after'] * 100)}%" for c in shown
        ]
        parts.append(f"sector allocation shifted: {', '.join(formatted)}")
    if holding_count_change is not None:
        parts.append(
            f"holding count changed from {holding_count_change['before']} "
            f"to {holding_count_change['after']}"
        )
    if not parts:
        return f"{sentence}, no meaningful change in composition."
    return f"{sentence}, {' and '.join(parts)}."


def _diff(prev: PortfolioSnapshot, curr: PortfolioSnapshot) -> dict | None:
    sector_changes = _sector_changes(prev, curr)
    holding_count_change = _holding_count_change(prev, curr)

    if not sector_changes and holding_count_change is None:
        return None  # nothing meaningfully changed between these two syncs

    return {
        "from_date": prev.snapshot_date.isoformat(),
        "to_date": curr.snapshot_date.isoformat(),
        "sector_changes": sector_changes,
        "holding_count_change": holding_count_change,
        "summary": _summary(
            prev.snapshot_date, curr.snapshot_date, sector_changes, holding_count_change
        ),
    }
