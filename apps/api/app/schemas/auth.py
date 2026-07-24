"""Auth schemas — request validation for the auth blueprint.

Uses marshmallow for validation. Schema classes raise ValidationError on
invalid input; routes catch this and return a 400.
"""

from marshmallow import Schema, ValidationError, fields, validate, validates


class RegisterSchema(Schema):
    email = fields.Email(required=True)
    password = fields.String(required=True, validate=validate.Length(min=8, max=128))
    username = fields.String(
        required=True,
        validate=[
            validate.Length(min=3, max=50),
            validate.Regexp(
                r"^[a-zA-Z0-9_-]+$",
                error="Username may only contain letters, digits, underscores, and hyphens.",
            ),
        ],
    )

    @validates("password")
    def validate_password_strength(self, value: str) -> str:
        # Basic strength check — at least one letter and one digit.
        has_letter = any(c.isalpha() for c in value)
        has_digit = any(c.isdigit() for c in value)
        if not (has_letter and has_digit):
            raise ValidationError("Password must contain at least one letter and one digit.")
        return value


class LoginSchema(Schema):
    email = fields.Email(required=True)
    password = fields.String(required=True)
