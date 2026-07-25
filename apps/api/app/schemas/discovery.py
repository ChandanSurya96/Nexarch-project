"""Discovery feed query-param validation. See docs/api.md "Discovery"."""

from marshmallow import Schema, fields, validate


class DiscoveryQuerySchema(Schema):
    strategy = fields.String(load_default=None, allow_none=True)
    sort = fields.String(
        load_default="recency",
        validate=validate.OneOf(["recency", "portfolio_age", "alphabetical"]),
    )
    page = fields.Integer(load_default=1, validate=validate.Range(min=1))
    per_page = fields.Integer(load_default=20, validate=validate.Range(min=1, max=100))
