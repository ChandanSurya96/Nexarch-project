"""Shared pagination query-param schema — reused by every paginated list
endpoint (see docs/api.md "Pagination") so the page/per_page contract
(bounds, defaults) can't drift between endpoints."""

from marshmallow import Schema, fields, validate


class PaginationQuerySchema(Schema):
    page = fields.Integer(load_default=1, validate=validate.Range(min=1))
    per_page = fields.Integer(load_default=20, validate=validate.Range(min=1, max=100))
