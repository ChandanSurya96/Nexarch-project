"""Error tracking via Sentry (ADR-041).

Entirely opt-in: if `SENTRY_DSN` is unset — which it is by default, in every
environment, until an operator sets it — this does nothing at all. No client
is created, no network call is made, nothing is sent anywhere. That property
is deliberate, because it means this can ship and be reviewed before anyone
has created a Sentry account, and local development and CI never talk to a
third party.

Slice 2 (ADR-034) built structured JSON logs and a per-request correlation
id but deliberately wired in no external service, since there was nowhere to
alert into and picking a vendor was tied to the hosting decision. This closes
that, and reuses the same correlation id as a Sentry tag so a log line and a
Sentry event for the same request can be matched up.

What is NOT sent: `send_default_pii` stays off, so Sentry receives no
request bodies, cookies, or user identifiers by default. That matters here
more than in a typical app — request bodies on this API carry passwords
(`/auth/login`, `/auth/register`) and broker OAuth codes
(`/broker-connections/callback`). See docs/security.md.
"""

from __future__ import annotations

from flask import Flask


def configure_monitoring(app: Flask) -> None:
    """Initialise Sentry if — and only if — a DSN is configured."""
    dsn = app.config.get("SENTRY_DSN")
    if not dsn:
        return

    try:
        import sentry_sdk
        from sentry_sdk.integrations.celery import CeleryIntegration
        from sentry_sdk.integrations.flask import FlaskIntegration
    except ImportError:  # pragma: no cover - dependency is in requirements.txt
        app.logger.warning("SENTRY_DSN is set but sentry-sdk is not installed; skipping.")
        return

    sentry_sdk.init(
        dsn=dsn,
        environment=app.config.get("SENTRY_ENVIRONMENT", "production"),
        release=app.config.get("APP_RELEASE"),
        integrations=[FlaskIntegration(), CeleryIntegration()],
        # Off by design — see this module's docstring. Request bodies on this
        # API include passwords and broker OAuth codes.
        send_default_pii=False,
        traces_sample_rate=float(app.config.get("SENTRY_TRACES_SAMPLE_RATE", 0.0)),
        before_send=_scrub_event,
    )

    @app.before_request
    def _tag_request_id() -> None:
        # Correlates a Sentry event with the JSON log lines for the same
        # request (ADR-034's X-Request-ID).
        from flask import g

        request_id = g.get("request_id")
        if request_id:
            sentry_sdk.set_tag("request_id", request_id)


_SENSITIVE_KEYS = {
    "password",
    "access_token",
    "refresh_token",
    "auth_code",
    "authorization",
    "jwt_secret",
    "encryption_kms_key_id",
    "api_key",
    "api_secret",
    "csrf_token",
}


def _scrub_event(event: dict, hint: dict) -> dict | None:
    """Belt-and-braces scrub of anything secret-shaped before it leaves.

    `send_default_pii=False` already covers the documented cases; this is a
    second layer for values that reach an event some other way (an exception
    message, a manually-set extra). The same rule audit_service and
    price_cache_service already follow: secrets never leave the process.
    """
    for section in ("extra", "request"):
        data = event.get(section)
        if isinstance(data, dict):
            _redact_in_place(data)
    return event


def _redact_in_place(data: dict) -> None:
    for key, value in list(data.items()):
        if key.lower() in _SENSITIVE_KEYS:
            data[key] = "[redacted]"
        elif isinstance(value, dict):
            _redact_in_place(value)
