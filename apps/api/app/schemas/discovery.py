"""Discovery feed query-param validation. See docs/api.md "Discovery"."""

from marshmallow import fields, validate

from app.schemas.pagination import PaginationQuerySchema


class DiscoveryQuerySchema(PaginationQuerySchema):
    strategy = fields.String(load_default=None, allow_none=True)
    sort = fields.String(
        load_default="recency",
        validate=validate.OneOf(["recency", "portfolio_age", "alphabetical"]),
    )
