"""Response helpers.

Every endpoint returns the same envelope:
    { "data": ..., "meta": {}, "error": null }

Use these helpers instead of building the dict manually so the shape is
guaranteed consistent across all routes.

See docs/api.md "Response Envelope".
"""

from flask import jsonify
from flask.wrappers import Response


def format_validation_error(messages: object) -> str:
    """Flatten a marshmallow ValidationError's messages into one readable sentence.

    Every route previously passed `str(exc.messages)` straight into the error
    envelope. marshmallow's `messages` is a dict of field -> list of errors, so
    `str()` produced a Python repr — the register form rendered
    `{'password': ['Password must contain at least one letter and one digit.']}`
    verbatim, braces and quotes included, on the first screen a new user sees.

    marshmallow's own messages are already written as sentences, so the field
    name is only prefixed when the sentence doesn't already name it — that
    keeps "Password must contain..." clean while still giving "Missing data for
    required field." something to attach to.
    """
    if not isinstance(messages, dict):
        return str(messages) or "Invalid request."

    parts: list[str] = []
    for field, errors in sorted(messages.items(), key=lambda kv: str(kv[0])):
        label = str(field).replace("_", " ").strip().capitalize()
        # Nested schemas yield a dict here rather than a list; recursing keeps
        # the output flat instead of leaking a repr one level down.
        if isinstance(errors, dict):
            parts.append(f"{label}: {format_validation_error(errors)}")
            continue
        for err in errors if isinstance(errors, list | tuple) else [errors]:
            text = str(err).strip()
            if label.lower() in text.lower():
                parts.append(text)
            else:
                parts.append(f"{label}: {text}")

    return " ".join(parts) or "Invalid request."


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
