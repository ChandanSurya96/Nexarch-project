"""Discovery feed — browse public/verified portfolios by strategy.

See docs/product-requirements.md "Feature: Investor Discovery Feed":
filters via the strategy_categories many-to-many, pagination, sort by
recency/portfolio-age/alphabetical (NOT "most followed" — that's an
explicit Phase 2+ addition, see the same doc).

Cached in Redis with a short TTL, invalidated wholesale on any sync
completion (see docs/architecture.md "Caching Strategy"). Clearing the
whole discovery cache namespace rather than tracking exactly which
filter/sort/page combinations include the affected portfolio is a
deliberate simplification — revisit only if cache-miss volume from this
becomes a real cost at scale.
"""

from __future__ import annotations

import json

from sqlalchemy import func
from sqlalchemy.orm import selectinload

from app.extensions import redis_client
from app.models.portfolio import Portfolio
from app.models.public_investor import PublicInvestor
from app.models.strategy_category import PortfolioStrategyTag, StrategyCategory
from app.models.user import User
from app.schemas.portfolio import DiscoveryInvestorSchema
from app.services.portfolio_service import get_latest_snapshots_for

_CACHE_TTL_SECONDS = 60
_CACHE_KEY_PREFIX = "discovery:investors:"
# Only the first few pages are cached (ADR-038). The cache key includes
# `page`, which is caller-controlled and unbounded, so caching every page
# lets a crawler mint unlimited Redis keys — each held for the TTL — purely
# by walking ?page=1..N. Real traffic overwhelmingly hits the first pages;
# deep pages fall through to the database, which is correct behaviour, just
# uncached. per_page is already bounded to 100 by the schema.
_MAX_CACHEABLE_PAGE = 5

_SORT_OPTIONS = {"recency", "portfolio_age", "alphabetical"}


def list_investors(
    strategy_slug: str | None, sort: str, page: int, per_page: int
) -> tuple[list[dict], int]:
    """Returns (page of serialized portfolios, total count).

    sort: one of "recency" | "portfolio_age" | "alphabetical" (default "recency").
    """
    sort = sort if sort in _SORT_OPTIONS else "recency"
    is_cacheable = page <= _MAX_CACHEABLE_PAGE
    cache_key = f"{_CACHE_KEY_PREFIX}{strategy_slug}:{sort}:{page}:{per_page}"

    if is_cacheable:
        cached = redis_client.get(cache_key)
        if cached is not None:
            results, total = json.loads(cached)
            return results, total

    query = Portfolio.query.filter(Portfolio.is_public.is_(True))

    if strategy_slug:
        # Filtering on one specific slug via the composite-PK-backed join
        # can't produce more than one matching row per portfolio, so this
        # never needs DISTINCT — which matters below, since Postgres (unlike
        # SQLite) rejects SELECT DISTINCT combined with an ORDER BY
        # expression that isn't in the select list (the alphabetical sort
        # below hits exactly that).
        query = (
            query.join(PortfolioStrategyTag, PortfolioStrategyTag.portfolio_id == Portfolio.id)
            .join(
                StrategyCategory,
                StrategyCategory.id == PortfolioStrategyTag.strategy_category_id,
            )
            .filter(StrategyCategory.slug == strategy_slug)
        )

    # Count before adding sort/eager-load — independent of both, and the
    # alphabetical sort's joins are irrelevant to a row count.
    total = query.with_entities(Portfolio.id).count()

    # Deliberately NOT eager-loading Portfolio.snapshots (ADR-036): the only
    # thing this feed needs from snapshots is each portfolio's *latest*
    # health_metrics, and loading the collection to get it meant
    # materializing every snapshot ever taken for every portfolio on the page
    # — 7,300 ORM objects for a 20-item page at one year of daily syncs, and
    # unbounded growth after that. Fetched below in one query instead.
    query = query.options(
        selectinload(Portfolio.user),
        selectinload(Portfolio.public_investor),
        selectinload(Portfolio.strategy_tags).selectinload(PortfolioStrategyTag.strategy_category),
    )

    if sort == "recency":
        query = query.order_by(Portfolio.updated_at.desc())
    elif sort == "portfolio_age":
        query = query.order_by(Portfolio.created_at.asc())
    else:  # alphabetical — needs the owner joins to sort on a name
        query = (
            query.outerjoin(User, Portfolio.user_id == User.id)
            .outerjoin(PublicInvestor, Portfolio.public_investor_id == PublicInvestor.id)
            .order_by(func.coalesce(PublicInvestor.name, User.display_name, User.username).asc())
        )

    portfolios = query.offset((page - 1) * per_page).limit(per_page).all()

    # One query for the whole page's latest snapshots, handed to the schema
    # via context (ADR-036) — replaces per-portfolio collection loading.
    # Instantiated per call rather than mutating a module-level schema's
    # .context: that instance would be shared across concurrent requests, so
    # assigning to it is a race (one request's snapshots serialized into
    # another's response).
    latest_snapshots = get_latest_snapshots_for([p.id for p in portfolios])
    investor_schema = DiscoveryInvestorSchema(context={"latest_snapshots": latest_snapshots})
    results = investor_schema.dump(portfolios, many=True)
    if is_cacheable:
        redis_client.set(cache_key, json.dumps((results, total)), ex=_CACHE_TTL_SECONDS)
    return results, total


def list_strategy_categories() -> list[StrategyCategory]:
    return StrategyCategory.query.order_by(StrategyCategory.name.asc()).all()


def invalidate_discovery_cache() -> None:
    """Called on sync completion (see sync_service.run_sync)."""
    redis_client.scan_delete(f"{_CACHE_KEY_PREFIX}*")
