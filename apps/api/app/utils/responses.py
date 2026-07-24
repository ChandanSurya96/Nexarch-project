"""Response helpers.

Every endpoint returns the same envelope:
    { "data": ..., "meta": {}, "error": null }

Use these helpers instead of building the dict manually so the shape is
guaranteed consistent across all routes.

See docs/api.md "Response Envelope".
"""

from flask import jsonify
from flask.wrappers import Response


def success(data: object, meta: dict | None = None, status: int = 200) -> tuple[Response, int]:
    """Return a successful JSON response."""
    return (
        jsonify({"data": data, "meta": meta or {}, "error": None}),
        status,
    )


def error(code: str, message: str, status: int) -> tuple[Response, int]:
    """Return an error JSON response.

    Args:
        code: Machine-readable UPPER_SNAKE_CASE error code for the frontend to switch on.
        message: Human-readable description — may change wording without being a breaking change.
        status: HTTP status code.
    """
    return (
        jsonify(
            {
                "data": None,
                "meta": {},
                "error": {"code": code, "message": message, "status": status},
            }
        ),
        status,
    )
