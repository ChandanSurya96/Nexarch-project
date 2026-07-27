"""Structured (JSON) application logging — see docs/security.md "Incident
Response Basics" (ADR-034). A hand-rolled formatter, not a new dependency:
the shape needed here (timestamp, level, logger name, message, request_id,
user_id, exception info) is simple enough that a third-party JSON-logging
library isn't worth the added dependency surface, and hand-rolling it keeps
full control over what a log record can ever contain — never token values
or password material, the same rule app/services/audit_service.py already
states for the audit_logs table.

Every app.logger.* call (routes, services, error_handlers) goes through
this configuration; audit_logs stays the durable/queryable security-and-ops
record, this is the live tail.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime

from flask import Flask, g, has_app_context, has_request_context, request


class _RequestContextFilter(logging.Filter):
    """Attaches request_id/user_id to every log record, when available.

    Must never raise — a logging Filter that raises has its exception
    swallowed by the logging module itself (Handler.handleError), which
    silently drops the record. has_app_context() guards "no Flask context
    at all" (e.g. code that runs before the first request); g.get(...,
    "-") guards "a context IS active but request_id was never set" — the
    Celery-task case, since before_request only fires for real HTTP
    requests, not task execution.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        if has_app_context():
            record.request_id = g.get("request_id", "-")
            record.user_id = g.get("user_id", "-")
        else:
            record.request_id = "-"
            record.user_id = "-"
        return True


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", "-"),
            "user_id": getattr(record, "user_id", "-"),
        }
        if has_request_context():
            payload["method"] = request.method
            payload["path"] = request.path
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def configure_logging(app: Flask) -> None:
    """Replace Flask's default plain-text logger with structured JSON.

    Called once from create_app(). Level comes from LOG_LEVEL (default
    INFO) so verbosity can change per environment without a code change.
    """
    handler = logging.StreamHandler()
    handler.setFormatter(_JsonFormatter())
    handler.addFilter(_RequestContextFilter())

    app.logger.handlers = [handler]
    app.logger.setLevel(app.config.get("LOG_LEVEL", "INFO"))
    app.logger.propagate = False
