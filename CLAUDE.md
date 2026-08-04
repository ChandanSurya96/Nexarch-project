# Nexarch — operating guide

Portfolio identity & investor-discovery platform for India — read-only broker sync, verified investor profiles, public investor library. No trade execution, no copy trading, no single "trust score."

This file is **how to work here**: rules, structure, conventions, commands. It deliberately holds nothing volatile.

**For what is true today** — stage, status, open PRs, blockers, priorities, test and CI results — read **@docs/CURRENT_STATE.md**. Read it before starting anything. If this file and that one disagree about status, that one is right.

Stack: Next.js + TypeScript + Tailwind (frontend) · Flask + SQLAlchemy + PostgreSQL + Redis/Celery (backend) · JWT auth.

## Where to start

| Question | Document |
|---|---|
| What's the state of the project right now? | [docs/CURRENT_STATE.md](docs/CURRENT_STATE.md) |
| Why is it built this way? | [docs/decisions.md](docs/decisions.md) — 50 ADRs |
| What am I not supposed to build yet? | [docs/roadmap.md](docs/roadmap.md) |
| How does the system fit together? | [docs/architecture.md](docs/architecture.md) |
| What's already known to be broken or owed? | [docs/TECHNICAL_DEBT.md](docs/TECHNICAL_DEBT.md) |
| What trap is about to cost me an hour? | [docs/OPERATIONAL_GOTCHAS.md](docs/OPERATIONAL_GOTCHAS.md) |
| Everything else | [docs/README.md](docs/README.md) indexes all of it |

## Non-negotiable rules

These are product and compliance boundaries, not preferences. Don't cross one because it would be convenient; if one seems wrong, raise it rather than route around it.

- **No single composite "trust score"** — only labelled, separately-explained portfolio-health indicators. A composite number ranks investors, which is the thing this product exists not to do. (docs/product-requirements.md, ADR-007)
- **Copy about a portfolio's strategy or performance stays descriptive and historical** — never a recommendation, never a promise of returns. SEBI's finfluencer enforcement (2024–2026) sits exactly on this line. (docs/security.md)
- **New broker connections default `is_public = false`**, and that default does not change without an explicit instruction — the broker data-vending question (ADR-011) is still open.
- **Never scrape a broker's app or site** in place of a real API or the Account Aggregator path. (docs/broker-integrations.md)
- **Nothing from Phase 2+** (execution, copy trading, subscriptions, notifications, chat, community posts) gets built unless explicitly asked. (docs/roadmap.md)
- **Never present fabricated records as real** — filings, registration numbers, holdings, testimonials — and never attribute them to a real person or organisation. Sample data is named as sample data.
- **Never invent data to fill a UI.** If a field is unavailable, render nothing and document which backend field would enable it. No placeholder allocations, no equal-weight fallbacks, no shapes derived from unrelated numbers. On a product whose entire claim is "this is what they actually hold", an invented visualisation is worse than an absent one. (ADR-048)

## Working process

- **Read the doc that owns the area before touching it.** docs/README.md indexes them. Don't re-derive architecture, schema, or API shape that is already written down.
- **Plan first for anything spanning more than one file** — new endpoint, schema change, new integration, refactor. Wait for approval before editing. Default to Plan Mode.
- **Record real decisions as ADRs.** A library choice, a tradeoff, a scoping call — write it to docs/decisions.md before or alongside implementing. Undocumented decisions are how this codebase would lose its reasoning.
- **Verify against the implementation, never against the docs.** Documentation asserting a guarantee the code doesn't deliver has been found repeatedly here: forgeable JWTs, CSRF documented but off, rate limiting documented but absent, a contrast pass that was never run, a Framer Motion dependency that wasn't installed, and endpoints in api.md that don't exist. When docs and code disagree, the code is the fact and the doc is the bug.
- **Measure before claiming.** "Faster", "passes contrast", "no longer leaks timing" are measurements, not opinions. Reproduce a bug before fixing it, and re-measure after.
- **If a reported issue turns out not to exist, say so and don't "fix" it.**
- **Fix drift in the same PR you notice it.** A doc that has drifted is worse than no doc, because it reads as authoritative.

## Repository structure

`apps/web` is a **git submodule** (`ChandanSurya96/nexarch-web`). This repository tracks a commit pointer, not the frontend's files — so a frontend change is **two commits and two pushes**, and a clone needs `--recurse-submodules`. See docs/OPERATIONAL_GOTCHAS.md.

```
apps/api/          Flask backend — this repo
  app/
    models/        SQLAlchemy models (docs/database.md)
    routes/        One blueprint per domain (docs/api.md)
    services/      Business logic — routes stay thin
    schemas/       Request/response validation
    integrations/  broker/ (one adapter per broker) + account_aggregator/
    tasks/         Celery jobs
    utils/
  migrations/      Alembic
  tests/
apps/web/          Next.js frontend — SUBMODULE, separate repo
  app/             App Router pages
  components/ui/       Design-system primitives — every page composes from these
  components/landing/  Marketing page only, scoped styles
  lib/             API client, hooks, formatting
  styles/          globals.css (product) + landing.css (landing only)
docs/              Single source of truth for the project
scripts/           Ops and benchmark scripts
infra/             Deployment configs (currently empty)
.github/workflows/ CI + deploy
```

## Architecture rules

**Backend**

- **Routes stay thin; services hold the logic.** A route validates, calls one service, and shapes a response. Two routes needing the same behaviour call the same service rather than each implementing it — this is why analytics and discovery can never disagree about a portfolio's health.
- **Every response uses the documented envelope** — `{ data, meta, error }`, on success *and* failure. (docs/api.md)
- **Broker specifics live behind an adapter.** `integrations/broker/base.py` defines the interface, `registry.py` is the only lookup point. Adding a broker means registering an adapter, never touching callers.
- **A new Postgres ENUM value needs its own migration.** SQLite doesn't enforce enums, so a missing `ALTER TYPE` is invisible locally and a 500 in production. This has shipped twice. (docs/OPERATIONAL_GOTCHAS.md)
- **Redis is a cache, not a dependency to die on.** Every Redis call needs a degraded path — this failure mode has caused three separate production bugs. `/health` must stay green when Redis is down; `/health/ready` must not.
- **Background sync is the pipeline whose worst failure is silence.** If it stops, nothing raises and every other endpoint stays green. `/health/sync` exists for exactly this. (ADR-047)

**Frontend**

- **Pages compose from `components/ui` primitives** — `PageContainer`, `PageHeader`, `PageSection`, `Surface`, `Metric`, `StatCard`. Never hand-roll a page shell, card, heading or metric style. If a screen needs a shape the primitives don't have, extend a primitive rather than opting out. (docs/design-system.md, ADR-048)
- **Landing-page styling is scoped to `.landing`** in `styles/landing.css`. Its `--l-*` tokens don't leak into the product UI, and product tokens don't apply there. (ADR-049)
- **Framer Motion only on the landing route, through `LazyMotion` + `m`.** `motion.*` throws there under `strict`. Product-UI motion stays CSS. (ADR-050)
- **Every colour pair measures ≥ 4.5:1** (3:1 for large text and non-text), measured against composited alpha in the live DOM. Arithmetic on tokens has been wrong twice.
- **Every page needs a `<main id="main">`** — including auth-guarded fallback states, or the global skip link becomes a dead link.

## Coding conventions

- TypeScript strict mode; no unexplained `any`. camelCase in TS/JS, snake_case in Python.
- Small, single-purpose functions. A service doing three unrelated things is three functions.
- **Comments explain why, not what.** The valuable comment here records a constraint that isn't visible from the code — why a value deviates from a spec, why an exemption is load-bearing, why an alternative was rejected.
- No duplication. The same logic in an adapter and a service belongs in one place.
- Conventional Commits: `feat:` / `fix:` / `docs:` / `chore:` / `refactor:`
- Trunk-based: short-lived branches off `main`, merged via PR. Never push directly to `main`.

## Operational rules

Each of these has cost real time. Full explanations in docs/OPERATIONAL_GOTCHAS.md.

- **Run `black`/`ruff` from `apps/api`, with paths inside it.** A path outside moves the config root to the repo root, which has no `pyproject.toml`, and silently reformats at line-length 88 instead of 100. The round trip is lossy — the only fix is `git checkout`. This has hit 68 files once.
- **There is no Prettier here** — not a dependency, no config. Don't reach for `npx prettier`; it reformats at its own defaults. `next lint` is the frontend's formatter of record.
- **Never run `npm run build` while `npm run dev` is running** — they share `.next` and the build clobbers the dev server's chunks. Stop dev and clear `.next` when switching modes.
- **Start Docker before running backend tests.** Without Postgres and Redis, 61 tests fail as `TypeError: 'NoneType' object is not subscriptable`, which reads as application bugs.
- **`apps/api/.env` must exist** or pytest aborts during collection with a SQLAlchemy URL error. It's gitignored, so a fresh clone has none.
- **Use the venv interpreter by path** (`./venv/Scripts/python.exe -m pytest`); `source venv/Scripts/activate` has silently failed to switch interpreters here.
- **Never commit a real secret.** `.env.example` holds placeholders only. Secrets live in GitHub/Railway/Vercel secret stores. Don't paste real values into a chat, ticket, or log.

## Commands

Backend, from `apps/api/` (prefix with `./venv/Scripts/python.exe -m` on Windows):

```bash
flask run                                          # dev server
celery -A app.celery_app worker --loglevel=info    # sync worker
celery -A app.celery_app beat --loglevel=info      # scheduled sync
pytest                                             # tests (needs Docker up)
ruff check app/                                    # lint
black app/                                         # format
flask db upgrade                                   # apply migrations
flask db migrate -m "..."                          # generate a migration
```

Frontend, from `apps/web/`:

```bash
npm run dev          # dev server
npm run build        # production build (never while dev is running)
npm run lint         # ESLint via next lint
npm run type-check   # tsc --noEmit
npm test             # vitest
```

Infra, from the project root:

```bash
docker compose up -d   # Postgres 15 + Redis 7
```

## Before calling something done

CI is the enforcement point, and [docs/CURRENT_STATE.md](docs/CURRENT_STATE.md) records whether it is currently running. Either way, run the checks locally and report what you actually saw — including failures.

1. `docker compose up -d`
2. Backend: `pytest`, `ruff check app/`, `black --check app/`
3. Frontend: `npm run lint`, `npm run type-check`, `npm test`, `npm run build`
4. Docs updated in the same change — including CURRENT_STATE.md if status, blockers, or results moved
5. An ADR written for any real decision

Report outcomes faithfully. If a step was skipped or blocked, say which and why. A claim of "verified" that wasn't measured is the failure mode this project has spent three slices removing.
