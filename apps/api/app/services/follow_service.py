"""Following — no capital, no execution relationship.

See docs/product-requirements.md "Feature: Following": following a
portfolio never moves money or places an order. This module only ever
creates/deletes a Follow row.
"""

from __future__ import annotations

import uuid

from sqlalchemy.orm import selectinload

from app.extensions import db
from app.models.follow import Follow
from app.models.portfolio import Portfolio
from app.models.strategy_category import PortfolioStrategyTag
from app.services.portfolio_service import PortfolioAccessError, get_visible_portfolio


def follow(user_id: uuid.UUID, portfolio_id: uuid.UUID) -> Follow:
    """Follow a portfolio. Idempotent — following twice is a no-op, not an error.

    Raises PortfolioAccessError (PORTFOLIO_NOT_FOUND) if the portfolio
    doesn't exist or isn't visible to this user — you can't follow what
    you can't see. Raises PortfolioAccessError (CANNOT_FOLLOW_OWN_PORTFOLIO)
    if the portfolio belongs to the caller — following yourself isn't a
    real relationship, the same way it isn't on any other social feature.
    """
    portfolio = get_visible_portfolio(portfolio_id, user_id)
    if portfolio.user_id == user_id:
        raise PortfolioAccessError(
            "CANNOT_FOLLOW_OWN_PORTFOLIO", "You can't follow your own portfolio.", 400
        )

    existing = Follow.query.filter_by(
        follower_user_id=user_id, followed_portfolio_id=portfolio_id
    ).first()
    if existing is not None:
        return existing

    entry = Follow(follower_user_id=user_id, followed_portfolio_id=portfolio_id)
    db.session.add(entry)
    db.session.commit()
    return entry


def unfollow(user_id: uuid.UUID, portfolio_id: uuid.UUID) -> None:
    """Unfollow a portfolio. Idempotent — unfollowing something you don't
    follow is a no-op, not an error."""
    Follow.query.filter_by(follower_user_id=user_id, followed_portfolio_id=portfolio_id).delete()
    db.session.commit()


def list_following(user_id: uuid.UUID, page: int, per_page: int) -> tuple[list[Portfolio], int]:
    """Portfolios the user follows, paginated. Returns (page of results, total count).

    Eager-loads the same relationships PortfolioSchema's display_name/
    strategy_tags fields need, to avoid an N+1 across the list (see
    discovery_service.list_investors for the same pattern).
    """
    query = Portfolio.query.join(Follow, Follow.followed_portfolio_id == Portfolio.id).filter(
        Follow.follower_user_id == user_id
    )
    total = query.count()
    portfolios = (
        query.options(
            selectinload(Portfolio.user),
            selectinload(Portfolio.public_investor),
            selectinload(Portfolio.strategy_tags).selectinload(
                PortfolioStrategyTag.strategy_category
            ),
        )
        .order_by(Follow.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    return portfolios, total
