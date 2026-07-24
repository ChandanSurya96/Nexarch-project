"""User output schemas."""

from marshmallow import Schema, fields


class UserSchema(Schema):
    """Serializes a User for API responses (no sensitive fields)."""

    id = fields.UUID()
    email = fields.Email()
    username = fields.String()
    display_name = fields.String(allow_none=True)
    bio = fields.String(allow_none=True)
    avatar_url = fields.String(allow_none=True)
    is_public = fields.Boolean()
    created_at = fields.DateTime(format="iso")
    updated_at = fields.DateTime(format="iso")
