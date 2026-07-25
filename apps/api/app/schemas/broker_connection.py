"""Broker-connection request/response schemas."""

from marshmallow import Schema, fields, validate


class BrokerConnectionInitSchema(Schema):
    broker_name = fields.String(required=True, validate=validate.Length(min=1, max=50))


class BrokerConnectionCallbackSchema(Schema):
    broker_name = fields.String(required=True, validate=validate.Length(min=1, max=50))
    auth_code = fields.String(required=True, validate=validate.Length(min=1))


class BrokerConnectionSchema(Schema):
    """Serializes a BrokerConnection for API responses. Token fields are
    never included — they never leave the sync worker (see docs/security.md)."""

    id = fields.UUID()
    broker_name = fields.String()
    connection_method = fields.String()
    status = fields.String()
    connected_at = fields.DateTime(format="iso")
    last_synced_at = fields.DateTime(format="iso", allow_none=True)
    token_expires_at = fields.DateTime(format="iso", allow_none=True)
