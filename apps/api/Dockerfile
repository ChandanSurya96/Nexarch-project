# Nexarch API + sync worker (ADR-040).
#
# One image serves both the web process and the Celery worker, with the
# command deciding which. They share every dependency and all application
# code, so building them separately would only create room for the two to
# drift apart — and a worker running different code than the API is exactly
# the kind of bug that's miserable to diagnose.
#
#   API:    gunicorn --bind 0.0.0.0:$PORT wsgi:app   (the CMD default)
#   Worker: celery -A app.celery_app worker --loglevel=info
#   Beat:   celery -A app.celery_app beat --loglevel=info

FROM python:3.13-slim AS base

# - PYTHONDONTWRITEBYTECODE: no .pyc clutter in a layer that's read-only anyway
# - PYTHONUNBUFFERED: logs reach the platform's collector immediately rather
#   than sitting in a buffer, which matters for the structured logging in
#   ADR-034 to be useful during an incident
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# psycopg2 needs libpq at runtime. Using psycopg2-binary would avoid the
# build step, but the binary wheel is explicitly discouraged for production
# by psycopg's own maintainers, so build against the real libpq instead and
# drop the compiler afterwards.
RUN apt-get update \
    && apt-get install --no-install-recommends -y libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Dependencies in their own layer, before app code, so a source-only change
# doesn't reinstall everything.
COPY requirements.txt ./
RUN apt-get update \
    && apt-get install --no-install-recommends -y build-essential libpq-dev \
    && pip install --no-cache-dir -r requirements.txt \
    && apt-get purge -y --auto-remove build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY . .

# Run unprivileged: a container process has no reason to be root, and this
# limits what a code-execution bug in a dependency can reach.
RUN useradd --create-home --uid 10001 nexarch \
    && chown -R nexarch:nexarch /app
USER nexarch

ENV FLASK_APP=wsgi.py \
    FLASK_ENV=production \
    PORT=8000

EXPOSE 8000

# Uses the liveness endpoint from ADR-034 — deliberately /health and not
# /health/ready: this checks whether the process is alive, and a Postgres or
# Redis outage should not cause the platform to kill and restart an
# otherwise-healthy container.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import os,urllib.request,sys; \
sys.exit(0 if urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\",8000)}/health', timeout=4).status == 200 else 1)"

# Shell form so the platform's $PORT is expanded at runtime — but with `exec`
# so the shell REPLACES itself with gunicorn rather than staying as PID 1.
# Without exec, SIGTERM on shutdown goes to /bin/sh and gunicorn never sees
# it, so a deploy or scale-down kills in-flight requests instead of draining
# them. (Docker's JSONArgsRecommended warning is about exactly this; exec is
# the fix that keeps variable expansion.)
CMD exec gunicorn --bind "0.0.0.0:${PORT}" --workers 2 --threads 4 --timeout 60 --graceful-timeout 30 --access-logfile - wsgi:app
