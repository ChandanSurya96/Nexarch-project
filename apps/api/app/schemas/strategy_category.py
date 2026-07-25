"""StrategyCategory response schema."""

from marshmallow import Schema, fields


class StrategyCategorySchema(Schema):
    id = fields.UUID()
    name = fields.String()
    slug = fields.String()
    description = fields.String(allow_none=True)
