"""Public Investor Library — read-only list/detail.

See docs/product-requirements.md "Feature: Public Investor Library".
Seeding is a separate concern (scripts/seed_public_investors.py); this
module only serves already-seeded data.
"""

from __future__ import annotations

from sqlalchemy.orm import selectinload

from app.models.public_investor import PublicInvestor


def list_public_investors() -> list[PublicInvestor]:
    return (
        PublicInvestor.query.options(selectinload(PublicInvestor.portfolio))
        .order_by(PublicInvestor.name.asc())
        .all()
    )


def get_by_slug(slug: str) -> PublicInvestor | None:
    return (
        PublicInvestor.query.options(selectinload(PublicInvestor.portfolio))
        .filter_by(slug=slug)
        .first()
    )
