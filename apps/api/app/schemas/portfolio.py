"""Portfolio/Holding request/response schemas. See docs/api.md.

PortfolioSchema calls into app.services.portfolio_service for its computed
fields (display_name, strategy_tags) rather than duplicating that logic here
— the same resolution is also used by discovery_service, so the detail view,
the following list, and the discovery feed describe a portfolio identically
wherever they overlap.
"""

from marshmallow import Schema, fields

from app.services import portfolio_service


class HoldingSchema(Schema):
    id = fields.UUID()
    symbol = fields.String()
    isin = fields.String(allow_none=True)
    exchange = fields.String(allow_none=True)
    quantity = fields.Decimal(as_string=True)
    avg_cost_price = fields.Decimal(as_string=True, allow_none=True)
    sector = fields.String(allow_none=True)
    market_cap_category = fields.String(allow_none=True)
    as_of_date = fields.Date()


class PortfolioSchema(Schema):
    id = fields.UUID()
    portfolio_type = fields.String()
    is_public = fields.Boolean()
    display_name = fields.Method("get_display_name")
    strategy_tags = fields.Method("get_strategy_tags")
    created_at = fields.DateTime(format="iso")
    updated_at = fields.DateTime(format="iso")

    def get_display_name(self, portfolio) -> str:
        return portfolio_service.resolve_display_name(portfolio)

    def get_strategy_tags(self, portfolio) -> list[str]:
        return portfolio_service.resolve_strategy_tag_slugs(portfolio)


class DiscoveryInvestorSchema(PortfolioSchema):
    """The discovery feed's list-item shape — everything PortfolioSchema
    has, plus the latest health snapshot. Kept as a subclass (not a
    parallel, independently-maintained dict) so the two views can't drift."""

    health = fields.Method("get_health")

    def get_health(self, portfolio) -> dict | None:
        return portfolio_service.resolve_latest_health(portfolio)


class PortfolioUpdateSchema(Schema):
    is_public = fields.Boolean(required=True)


class PortfolioAnalyticsSchema(Schema):
    """Response shape for GET /portfolios/:id/analytics. See docs/api.md."""

    portfolio_id = fields.String()
    total_value = fields.Float(allow_none=True)
    sector_allocation = fields.Dict(keys=fields.String(), values=fields.Float())
    health = fields.Dict(allow_none=True)
    strategy_overview = fields.String(allow_none=True)
    as_of = fields.String(allow_none=True)


class ActivityEntrySchema(Schema):
    """Response shape for one entry of GET /portfolios/:id/activity (ADR-015)."""

    from_date = fields.String()
    to_date = fields.String()
    sector_changes = fields.List(fields.Dict(keys=fields.String(), values=fields.Raw()))
    holding_count_change = fields.Dict(allow_none=True)
    summary = fields.String()
