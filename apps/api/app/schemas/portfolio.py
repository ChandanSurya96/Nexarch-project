"""Portfolio/Holding request/response schemas. See docs/api.md."""

from marshmallow import Schema, fields


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
    created_at = fields.DateTime(format="iso")
    updated_at = fields.DateTime(format="iso")


class PortfolioUpdateSchema(Schema):
    is_public = fields.Boolean(required=True)
