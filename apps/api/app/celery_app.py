"""Celery application factory (ADR-005).

Run locally with (see docs/development-guide.md):
    celery -A app.celery_app worker --loglevel=info
    celery -A app.celery_app beat --loglevel=info

Tasks run inside a Flask app context so they can use db.session, mirroring
the routes -> services -> models layering the rest of the app uses (see
docs/architecture.md).
"""

from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

from app import create_app

flask_app = create_app()


def _make_celery(app) -> Celery:
    celery = Celery(
        app.import_name,
        broker=app.config["CELERY_BROKER_URL"],
        backend=app.config["CELERY_RESULT_BACKEND"],
    )
    # Deliberately NOT celery.conf.update(app.config) — Flask's config dict
    # includes the legacy uppercase CELERY_BROKER_URL/CELERY_RESULT_BACKEND
    # keys (see app/config.py), and Celery 5's config loader raises
    # ImproperlyConfigured if it sees both those and the new-style
    # broker_url/result_backend (set above via the constructor) at once.
    # It would also leak unrelated Flask settings (SECRET_KEY,
    # SQLALCHEMY_DATABASE_URI, ...) into Celery's config for no reason.

    class ContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)

    celery.Task = ContextTask

    # Daily scheduled sync — long-term holdings don't need intraday freshness
    # (see docs/broker-integrations.md "Refresh Strategy").
    celery.conf.beat_schedule = {
        "sync-all-active-connections-daily": {
            "task": "sync_all_active_connections",
            "schedule": crontab(hour=2, minute=0),
        },
    }
    return celery


celery_app = _make_celery(flask_app)

# Import task modules so they register with celery_app (must come after
# celery_app is constructed, since tasks decorate with @celery_app.task).
from app.tasks import sync  # noqa: E402, F401
