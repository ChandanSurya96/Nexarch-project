"""Portfolio read/update business logic — ownership and visibility checks.

See docs/product-requirements.md "Feature: Verified Portfolio Profile" —
private-by-default, and a private portfolio must not be visible to anyone
but its owner (not even leak its existence via a different error code, same
posture as auth_service's unified INVALID_CREDENTIALS — see docs/security.md).
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import func
from sqlalchemy.orm import aliased, selectinload

from app.extensions import db
from app.models.portfolio import Portfolio
from app.models.portfolio_snapshot import PortfolioSnapshot
from app.models.strategy_category import PortfolioStrategyTag


class PortfolioAccessError(Exception):
    def __init__(self, code: str, message: str, status: int) -> None:
        self.code = code
        self.message = message
        self.status = status
        super().__init__(message)


def get_visible_portfolio(
    portfolio_id: uuid.UUID,
    requesting_user_id: uuid.UUID | None,
    *,
    for_serialization: bool = False,
) -> Portfolio:
    """Return a portfolio if it's public or owned by the requester.

    Raises PORTFOLIO_NOT_FOUND (404) otherwise — deliberately the same error
    for "doesn't exist" and "exists but private," so a private portfolio's
    existence isn't leaked to a non-owner.

    for_serialization (ADR-036): eager-load exactly what PortfolioSchema
    reads — owner/public_investor for display_name, tags->category for
    strategy_tags — so dumping a portfolio doesn't fire a lazy load per
    relationship. Opt-in on purpose: most callers here (history, activity,
    analytics) fetch a portfolio only to enforce visibility and never
    serialize it, so eager-loading unconditionally just adds queries those
    paths pay for and throw away — measured at +3 queries on
    GET /:id/history alone. Snapshots and holdings are never eager-loaded
    here regardless; that's the over-fetching this slice exists to remove.
    """
    options = (
        (
            selectinload(Portfolio.user),
            selectinload(Portfolio.public_investor),
            selectinload(Portfolio.strategy_tags).selectinload(
                PortfolioStrategyTag.strategy_category
            ),
        )
        if for_serialization
        else ()
    )
    portfolio = db.session.get(Portfolio, portfolio_id, options=options)
    is_owner = (
        portfolio is not None
        and requesting_user_id is not None
        and (portfolio.user_id == requesting_user_id)
    )
    if portfolio is None or not (portfolio.is_public or is_owner):
        raise PortfolioAccessError("PORTFOLIO_NOT_FOUND", "Portfolio not found.", 404)
    return portfolio


def update_visibility(user_id: uuid.UUID, portfolio_id: uuid.UUID, is_public: bool) -> Portfolio:
    """Toggle is_public — owner only, per docs/product-requirements.md."""
    portfolio = db.session.get(Portfolio, portfolio_id)
    if portfolio is None or portfolio.user_id != user_id:
        raise PortfolioAccessError("PORTFOLIO_NOT_FOUND", "Portfolio not found.", 404)

    portfolio.is_public = is_public
    db.session.commit()
    return portfolio


def get_my_portfolio(user_id: uuid.UUID) -> Portfolio | None:
    """The signed-in user's own portfolio, or None.

    None is a normal, expected state (ADR-019) — a Portfolio row is only
    created lazily on first successful sync (see sync_service.run_sync), so
    every new signup, and even a user who just finished a broker connection
    seconds ago, legitimately has no Portfolio yet.
    """
    return Portfolio.query.filter_by(user_id=user_id).first()


def get_latest_snapshot(portfolio_id: uuid.UUID) -> PortfolioSnapshot | None:
    """The most recent snapshot. snapshot_date alone isn't unique per
    portfolio (ADR-025) — more than one sync can land on the same calendar
    date — so created_at is the tiebreaker that makes "latest" deterministic
    rather than whichever same-date row the database happens to return first.
    """
    return (
        PortfolioSnapshot.query.filter_by(portfolio_id=portfolio_id)
        .order_by(PortfolioSnapshot.snapshot_date.desc(), PortfolioSnapshot.created_at.desc())
        .first()
    )


def get_latest_snapshots_for(
    portfolio_ids: Sequence[uuid.UUID],
) -> dict[uuid.UUID, PortfolioSnapshot]:
    """The latest snapshot for each of many portfolios, in ONE query (ADR-036).

    Exists because the discovery feed needs "latest health" for a whole page
    of portfolios. Loading `portfolio.snapshots` per portfolio and picking the
    newest in Python meant materializing the entire snapshot history of every
    portfolio on the page — measured at 7,300 ORM objects for a 20-item page
    with a year of daily syncs, ~95% of that request's wall time, and growing
    forever. This returns exactly one row per portfolio instead.

    Ordering matches get_latest_snapshot() exactly — (snapshot_date,
    created_at) descending — so "latest" means the same thing here as it does
    everywhere else (ADR-025).

    Uses ROW_NUMBER() rather than Postgres's DISTINCT ON deliberately: SQLAlchemy
    *silently ignores* DISTINCT ON on SQLite (the test backend), which would have
    returned every snapshot instead of one per portfolio — and since the rows come
    back newest-first, naively keying them into a dict would have kept the OLDEST
    row per portfolio. That fails silently and only in tests, i.e. the worst
    possible way. ROW_NUMBER is supported by both backends, so prod and tests run
    the same logic.
    """
    if not portfolio_ids:
        return {}

    ranked = (
        db.session.query(
            PortfolioSnapshot,
            func.row_number()
            .over(
                partition_by=PortfolioSnapshot.portfolio_id,
                order_by=(
                    PortfolioSnapshot.snapshot_date.desc(),
                    PortfolioSnapshot.created_at.desc(),
                ),
            )
            .label("rank"),
        )
        .filter(PortfolioSnapshot.portfolio_id.in_(portfolio_ids))
        .subquery()
    )

    snapshot_alias = aliased(PortfolioSnapshot, ranked)
    rows = db.session.query(snapshot_alias).filter(ranked.c.rank == 1).all()
    return {row.portfolio_id: row for row in rows}


def get_snapshot_history(portfolio_id: uuid.UUID) -> list[PortfolioSnapshot]:
    """Oldest-to-newest snapshot history — powers GET /portfolios/:id/history,
    documented since Phase 0 but not built until Milestone 5. Raw data (every
    snapshot), distinct from the descriptive diffs activity_service produces
    from the same table. created_at as a secondary key (ADR-025) orders
    same-date rows by actual creation time instead of arbitrarily."""
    return (
        PortfolioSnapshot.query.filter_by(portfolio_id=portfolio_id)
        .order_by(PortfolioSnapshot.snapshot_date.asc(), PortfolioSnapshot.created_at.asc())
        .all()
    )


# ── Shared serialization helpers ──────────────────────────────────────────────
# Used by both PortfolioSchema (app/schemas/portfolio.py) and
# discovery_service.py, so the detail view, the following list, and the
# discovery feed describe a portfolio identically wherever they overlap.


def resolve_display_name(portfolio: Portfolio) -> str:
    """'Whose portfolio is this' — the public investor's name, or the
    owning user's display name/username."""
    if portfolio.portfolio_type == "public" and portfolio.public_investor is not None:
        return portfolio.public_investor.name
    if portfolio.user is not None:
        return portfolio.user.display_name or portfolio.user.username
    return "Unknown"


def resolve_strategy_tag_slugs(portfolio: Portfolio) -> list[str]:
    return [tag.strategy_category.slug for tag in portfolio.strategy_tags]


def resolve_latest_health(portfolio: Portfolio) -> dict | None:
    """The most recent snapshot's health_metrics, or None if nothing has
    synced yet — honestly absent, not a fabricated default.

    Callers serializing many portfolios at once (the discovery feed) should
    pass pre-resolved snapshots via DiscoveryInvestorSchema's context instead
    of relying on this fallback — see get_latest_snapshots_for(). This path
    issues one query for a single portfolio.

    Previously this did `max(portfolio.snapshots, key=snapshot_date)`, which
    was wrong twice over: it loaded the portfolio's whole snapshot history to
    pick one row, and it ignored `created_at`, so for two snapshots sharing a
    calendar date it could pick a *different* one than get_latest_snapshot()
    does — meaning the discovery feed and the analytics endpoint could report
    different health for the same portfolio, nondeterministically (ADR-025
    exists precisely to prevent that).
    """
    snapshot = get_latest_snapshot(portfolio.id)
    return snapshot.health_metrics if snapshot is not None else None
