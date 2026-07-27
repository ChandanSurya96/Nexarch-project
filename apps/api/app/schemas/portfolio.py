"""Portfolio/Holding request/response schemas. See docs/api.md.

PortfolioSchema calls into app.services.portfolio_service for its computed
fields (display_name, strategy_tags) rather than duplicating that logic here
— the same resolution is also used by discovery_service, so the detail view,
the following list, and the discovery feed describe a portfolio identically
wherever they overlap.
"""

import uuid

from marshmallow import Schema, ValidationError, fields

from app.schemas.pagination import PaginationQuerySchema
from app.services import portfolio_service


class FollowingQuerySchema(PaginationQuerySchema):
    """Query-param validation for GET /users/me/following — no extra
    filters yet, but kept as its own schema (not the bare pagination one
    directly) so a future filter/sort param has somewhere to go without
    changing every paginated endpoint's schema."""


class _PortfolioIdPairField(fields.Field):
    """A single query-string value of exactly two comma-separated portfolio
    ids — the wire shape GET /portfolios/compare?ids=a,b has always used."""

    def _deserialize(self, value, attr, data, **kwargs) -> list[uuid.UUID]:
        tokens = [token for token in str(value).split(",") if token]
        if len(tokens) != 2:
            raise ValidationError("`ids` must contain exactly two comma-separated portfolio ids.")
        try:
            return [uuid.UUID(token) for token in tokens]
        except ValueError as exc:
            raise ValidationError("`ids` must contain two valid portfolio ids.") from exc


class CompareQuerySchema(Schema):
    """Query-param validation for GET /portfolios/compare."""

    ids = _PortfolioIdPairField(required=True)


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
    # Rules-based auto-categorization (Milestone 7, ADR-028) — {"slug",
    # "name", "explanation"} per matched category. Always [] for Public
    # Investor Library portfolios (manually curated, not rule-derived).
    strategy_categorization = fields.List(fields.Dict(keys=fields.String(), values=fields.Raw()))


class ActivityEntrySchema(Schema):
    """Response shape for one entry of GET /portfolios/:id/activity (ADR-015)."""

    from_date = fields.String()
    to_date = fields.String()
    sector_changes = fields.List(fields.Dict(keys=fields.String(), values=fields.Raw()))
    holding_count_change = fields.Dict(allow_none=True)
    summary = fields.String()


class PortfolioHistoryEntrySchema(Schema):
    """One entry of GET /portfolios/:id/history (Milestone 5) — raw
    snapshot-level data over time, distinct from activity_service's
    descriptive diffs computed from the same portfolio_snapshots table."""

    snapshot_date = fields.Date()
    total_value = fields.Float(allow_none=True)
    diversification_score = fields.Method("get_diversification_score")
    volatility = fields.Method("get_volatility")

    def get_diversification_score(self, snapshot) -> float | None:
        return (snapshot.health_metrics or {}).get("diversification_score")

    def get_volatility(self, snapshot) -> float | None:
        return (snapshot.health_metrics or {}).get("volatility")
