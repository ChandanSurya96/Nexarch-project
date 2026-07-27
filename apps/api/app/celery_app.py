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
    # ADR-034 — without these, a worker crash/OOM mid-task silently loses
    # the sync forever: the message is acked (and gone) the instant it's
    # received (Celery/Redis default), regardless of whether the task ever
    # finishes. With acks_late, a message is only acked after the task
    # completes (success OR failure); if the worker dies first, Redis
    # redelivers it to another worker after the broker's visibility
    # timeout. task_reject_on_worker_lost explicitly rejects (triggering
    # redelivery) rather than silently acking when a worker is confirmed
    # lost. Safe to enable because run_sync is designed to be safely
    # re-run from scratch (see sync_service.py's own retry/idempotency
    # notes) — a redelivered task re-executes the whole function, not a
    # partial resume.
    celery.conf.task_acks_late = True
    celery.conf.task_reject_on_worker_lost = True
    return celery


celery_app = _make_celery(flask_app)

# Import task modules so they register with celery_app (must come after
# celery_app is constructed, since tasks decorate with @celery_app.task).
from app.tasks import sync  # noqa: E402, F401
