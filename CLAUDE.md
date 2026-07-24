# Nexarch

Portfolio identity & investor-discovery platform for India — read-only broker sync, verified investor profiles, public investor library. No trade execution, no copy trading, no single "trust score."

Full context, in reading order: @docs/README.md

Stack: Next.js + TypeScript + Tailwind (frontend) · Flask + SQLAlchemy + PostgreSQL + Redis/Celery (backend) · JWT auth.

## Working process
- Before touching an area, read the doc that owns it — docs/README.md indexes all of them. Don't infer architecture, schema, or API shape from scratch when it's already written down.
- For anything touching more than one file — new endpoint, schema change, new integration, refactor — plan first and wait for approval before editing. Default to Plan Mode for this.
- If you make a real decision that isn't already in the docs (a library choice, a tradeoff, a scoping call), write it to docs/decisions.md as a new ADR before or alongside implementing it. Don't leave decisions undocumented.

## Non-negotiable rules
- No single composite "trust score" — only labeled, separately-explained portfolio-health indicators. (docs/product-requirements.md, ADR-007)
- Copy describing a portfolio's strategy or performance stays descriptive/historical — never a recommendation or a promise of returns. (docs/security.md)
- New broker connections default `is_public = false`, and that default doesn't change without an explicit instruction — the broker data-vending question (ADR-011) is still open. (docs/decisions.md)
- Never scrape a broker's app/site in place of a real API or the Account Aggregator path. (docs/broker-integrations.md)
- Nothing from Phase 2+ (execution, copy trading, subscriptions, notifications, chat, community posts) gets built unless explicitly asked. (docs/roadmap.md)

## Conventions
- TypeScript strict mode; no unexplained `any`. camelCase in TS/JS, snake_case in Python.
- Conventional Commits: feat: / fix: / docs: / chore: / refactor:
- Small, single-purpose functions. Comments explain why, not what.

## Commands
Backend (from `apps/api/`, with venv active):
- Dev server: `flask run`
- Tests: `pytest`
- Lint: `ruff check app/` · Format: `black app/`
- Migrate: `flask db upgrade` (apply) · `flask db migrate -m "..."` (generate new)

Frontend (from `apps/web/`):
- Dev server: `npm run dev`

Infra (from project root):
- `docker compose up -d` — Postgres 15 + Redis 7
