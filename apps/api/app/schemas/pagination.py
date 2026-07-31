"""Shared pagination query-param schemas — reused by every paginated list
endpoint (see docs/api.md "Pagination") so the page/per_page contract
(bounds, defaults) can't drift between endpoints."""

from marshmallow import Schema, fields, validate


class PaginationQuerySchema(Schema):
    page = fields.Integer(load_default=1, validate=validate.Range(min=1))
    per_page = fields.Integer(load_default=20, validate=validate.Range(min=1, max=100))


class OptionalPaginationQuerySchema(Schema):
    """Pagination for endpoints that were unbounded before and must stay
    backward-compatible (ADR-038).

    Same bounds as PaginationQuerySchema, but with NO defaults: absent
    params load as None, which the route reads as "return everything, in
    the original un-enveloped shape." Supplying either param opts into a
    bounded slice plus meta.pagination. That keeps `GET
    /portfolios/:id/history` byte-identical for existing clients (the
    frontend history chart consumes the whole series) while giving anyone
    who needs it a way to bound the response.
    """

    page = fields.Integer(load_default=None, validate=validate.Range(min=1))
    per_page = fields.Integer(load_default=None, validate=validate.Range(min=1, max=100))
