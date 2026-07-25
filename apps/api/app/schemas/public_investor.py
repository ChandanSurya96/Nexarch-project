"""PublicInvestor response schema. See docs/database.md PUBLIC_INVESTORS."""

from marshmallow import Schema, fields


class PublicInvestorSchema(Schema):
    id = fields.UUID()
    name = fields.String()
    slug = fields.String()
    bio = fields.String(allow_none=True)
    source_disclosure_url = fields.String(allow_none=True)
    last_disclosure_update = fields.DateTime(format="iso", allow_none=True)
    # The linked Portfolio's id, so the frontend can link to /portfolios/:id
    # for holdings/allocation/health — this schema otherwise has no portfolio
    # reference at all, even though PublicInvestor.portfolio always exists
    # once seeded (ADR-022).
    portfolio_id = fields.Method("get_portfolio_id")

    def get_portfolio_id(self, investor) -> str | None:
        return str(investor.portfolio.id) if investor.portfolio else None
