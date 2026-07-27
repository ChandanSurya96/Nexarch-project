"""App-wide error handling — every failure returns the documented envelope.

Before this module, flask-jwt-extended's own default callbacks (missing
token, expired token, malformed token, ...) and Flask's own 404/405/500
responses bypassed app/utils/responses.py entirely, returning their own
un-enveloped JSON (or HTML) shape instead of the documented
{"data": null, "meta": {}, "error": {"code", "message", "status"}} (see
docs/api.md, ADR-029). This is the single most common failure mode in the
whole API (every protected route, on every expired token), so it's worth
its own module rather than scattering `@app.errorhandler` calls elsewhere.

register_error_handlers(app) is called once from create_app(), after
jwt.init_app(app) — the JWT loaders below override flask-jwt-extended's
own already-registered internal handlers (CSRFError/NoAuthorizationError/
ExpiredSignatureError/etc. all route to these loader callbacks, confirmed
by reading flask_jwt_extended's own jwt_manager.py), so registration order
relative to jwt.init_app doesn't matter for those specifically.
"""

from __future__ import annotations

from flask import Flask, current_app, request
from werkzeug.exceptions import HTTPException

from app.extensions import jwt
from app.utils.responses import error


def register_error_handlers(app: Flask) -> None:
    # ── JWT-specific rejections ────────────────────────────────────────────

    @jwt.unauthorized_loader
    def _unauthorized(error_string: str):
        # flask-jwt-extended routes both "no token at all" (NoAuthorizationError)
        # and "cookie present but CSRF header missing/wrong" (CSRFError) through
        # this same callback — distinguished only by the message text.
        if "csrf" in error_string.lower():
            return error("CSRF_TOKEN_MISSING", error_string, 401)
        return error("AUTHORIZATION_REQUIRED", error_string, 401)

    @jwt.invalid_token_loader
    def _invalid_token(error_string: str):
        return error("TOKEN_INVALID", error_string, 422)

    @jwt.expired_token_loader
    def _expired_token(jwt_header: dict, jwt_data: dict):
        token_type = jwt_data.get("type")
        if token_type == "refresh":
            return error(
                "REFRESH_TOKEN_EXPIRED", "Your session has expired. Please log in again.", 401
            )
        return error("ACCESS_TOKEN_EXPIRED", "Your access token has expired.", 401)

    @jwt.needs_fresh_token_loader
    def _needs_fresh_token(jwt_header: dict, jwt_data: dict):
        return error("FRESH_TOKEN_REQUIRED", "A fresh token is required for this action.", 401)

    @jwt.revoked_token_loader
    def _revoked_token(jwt_header: dict, jwt_data: dict):
        return error("TOKEN_REVOKED", "This token has been revoked.", 401)

    # ── Generic Flask/Werkzeug failures ────────────────────────────────────

    @app.errorhandler(404)
    def _not_found(exc: HTTPException):
        return error("NOT_FOUND", "The requested resource was not found.", 404)

    @app.errorhandler(405)
    def _method_not_allowed(exc: HTTPException):
        return error("METHOD_NOT_ALLOWED", "This method is not allowed for this endpoint.", 405)

    @app.errorhandler(HTTPException)
    def _http_exception(exc: HTTPException):
        # Catches everything else Werkzeug/extensions raise as an HTTPException
        # (e.g. flask-limiter's 429 TooManyRequests) that isn't more specifically
        # handled above — derives a stable code from the exception's own name.
        code = (exc.name or "HTTP_ERROR").upper().replace(" ", "_")
        return error(code, exc.description or exc.name or "Request failed.", exc.code or 500)

    @app.errorhandler(Exception)
    def _unhandled_exception(exc: Exception):
        # Never leak internal exception details to the client — log the real
        # exception server-side (request_id/user_id are attached by the
        # logging filter configured in app/logging_config.py, ADR-034),
        # return a generic message.
        current_app.logger.exception(
            "Unhandled exception: method=%s path=%s", request.method, request.path
        )
        return error("INTERNAL_SERVER_ERROR", "An unexpected error occurred.", 500)
