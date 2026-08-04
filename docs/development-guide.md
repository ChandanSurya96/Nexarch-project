# Development Guide

**Last verified: 2026-08-04** — setup steps, commands, project structure and the formatting toolchain checked against the repository.

**Purpose:** Everything needed to get Nexarch running locally, the complete proposed folder structure, and the standards for how code gets written, reviewed, and shipped. See [architecture.md](./architecture.md) for the reasoning behind the structure below.

---

## Prerequisites

- Node.js LTS (for the Next.js frontend)
- Python 3.11+ (for the Flask backend)
- PostgreSQL 15+
- Redis 7+
- Docker + Docker Compose (recommended for local Postgres/Redis, so nobody needs to install them natively)

## Local Setup

```bash
# clone and enter the repo — apps/web is a submodule, so --recurse-submodules
# is required; without it apps/web is an empty directory
git clone --recurse-submodules <repo-url> nexarch && cd nexarch

# (already cloned without it? `git submodule update --init --recursive`)

# start Postgres + Redis
docker compose up -d

# backend
cd apps/api
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env    # required — pytest aborts at collection without it
flask db upgrade        # run migrations
flask run

# sync worker (separate terminal, from apps/api — Milestone 2+)
celery -A app.celery_app worker --loglevel=info

# scheduled daily sync (separate terminal, from apps/api — Milestone 2+)
celery -A app.celery_app beat --loglevel=info

# frontend (separate terminal)
cd apps/web
npm install
cp .env.example .env.local
npm run dev
```

Everything else the frontend offers, from `apps/web`:

```bash
npm run lint          # ESLint via next lint
npm run type-check    # tsc --noEmit
npm test              # vitest run
npm run build         # production build
```

`build` and `dev` share the `.next` directory, and a build run while the dev
server is up will clobber the chunks it is serving — the symptom is a
`Cannot find module './42.js'` 500 on a route that worked a second ago. Stop
the dev server and delete `.next` before switching between the two.

## Environment Variables (`.env.example`)

```
# backend
DATABASE_URL=postgresql://localhost:5432/nexarch
REDIS_URL=redis://localhost:6379
JWT_SECRET=
JWT_ACCESS_TTL_MINUTES=15
JWT_REFRESH_TTL_DAYS=30
ENCRYPTION_KMS_KEY_ID=

# broker integrations (per adapter — see broker-integrations.md)
UPSTOX_API_KEY=
UPSTOX_API_SECRET=
UPSTOX_REDIRECT_URI=
DHAN_API_KEY=
ANGELONE_API_KEY=
FYERS_API_KEY=
GROWW_API_KEY=
ZERODHA_API_KEY=
ZERODHA_API_SECRET=

# account aggregator (see broker-integrations.md)
AA_CLIENT_ID=
AA_PROVIDER_BASE_URL=

# frontend
NEXT_PUBLIC_API_BASE_URL=http://localhost:5000/api/v1
```

Never commit an actual `.env` file — only `.env.example` with placeholder values, per [security.md](./security.md).

## Project Structure

`apps/web` is a **git submodule** pointing at `ChandanSurya96/nexarch-web`.
This repository tracks a commit pointer, not the frontend's files — so a
frontend change is two commits and two pushes (the submodule first, then the
pointer bump here), and a PR that touches both shows only a one-line hash
change for the web side.

```
nexarch/
├── apps/
│   ├── web/                        # Next.js frontend — SUBMODULE, own repo
│   │   ├── app/                    # App Router pages
│   │   ├── components/
│   │   │   ├── ui/                 # Composition primitives — every page
│   │   │   │                       #   composes from these (ADR-048)
│   │   │   ├── landing/            # Marketing page only (ADR-049/050)
│   │   │   ├── portfolio/
│   │   │   └── comparison/
│   │   ├── lib/                    # API client, hooks, formatting, utilities
│   │   ├── styles/                 # globals.css (product) + landing.css
│   │   └── public/
│   └── api/                        # Flask backend
│       ├── app/
│       │   ├── __init__.py         # app factory
│       │   ├── models/             # SQLAlchemy models (see database.md)
│       │   ├── routes/             # Blueprints per domain (see api.md)
│       │   ├── services/           # Business logic, called from routes
│       │   ├── schemas/            # Request/response validation
│       │   ├── integrations/
│       │   │   ├── broker/         # One adapter module per broker
│       │   │   └── account_aggregator/
│       │   ├── tasks/              # Celery jobs (sync, etc.)
│       │   └── utils/
│       ├── migrations/             # Alembic
│       └── tests/
├── docs/                           # this folder
├── scripts/                        # one-off / ops scripts
├── infra/                          # (currently empty — see below)
└── .github/workflows/              # CI + deploy
```

`infra/` holds only a `.gitkeep`. Deployment configuration lives in
`.github/workflows/` and `apps/api/Dockerfile` instead — the directory is
reserved, not populated. Don't go looking there for the deploy setup.

## Coding Standards

- **TypeScript strict mode** on the frontend; no `any` without a comment explaining why.
- **Naming:** camelCase in TS/JS, snake_case in Python — each language's own convention, not forced consistency across the boundary.
- **Functions small and single-purpose.** A service function that does three unrelated things should be three functions.
- **Comments explain *why*, not *what*** — the code should already say what it does.
- **No duplication** — if the same logic appears in a broker adapter and a service twice, it belongs in one shared place.

### Linting & Formatting

What is actually wired up, as distinct from what this section claimed for most
of the project's life:

- **Frontend: ESLint only**, via `next lint`, enforced in CI. **Prettier is
  not installed and has no config here** — running `npx prettier` will happily
  reformat the codebase at its own 80-column defaults, which has happened once
  and had to be reverted across 26 files. Don't. ESLint is the formatter of
  record.
- **Backend: Ruff (lint) + Black (format)**, enforced in CI, configured in
  `apps/api/pyproject.toml` at line-length 100. **Run both from `apps/api`
  with paths inside it.** Black resolves its config from the common parent of
  the paths given, so passing `../../scripts/` moves the root to the repo
  root, which has no `pyproject.toml` — it then silently reformats at the
  default 88. Re-running at 100 does *not* undo it; the magic trailing comma
  makes the round trip lossy, so the only fix is `git checkout`. This has cost
  68 files once already.
- **There are no pre-commit hooks.** CI is the only enforcement point.

## Git Workflow

- Trunk-based: short-lived feature branches off `main`, merged via PR.
- Branch naming: `feature/<short-description>`, `fix/<short-description>`, `chore/<short-description>`.
- PRs require passing CI (lint, tests) before merge; no direct pushes to `main`.
- **Frontend changes are two commits.** Commit and push inside `apps/web`
  first, then commit the resulting pointer bump here. Pushing only the parent
  leaves a pointer to a commit nobody else can fetch, and CI's checkout of the
  submodule fails. If the submodule commit is on a branch, the parent's
  pointer targets that branch — merge the frontend PR before merging the
  parent if you want the pointer to track `main`.

### Commit Messages

Conventional Commits:
```
feat: add broker connection init endpoint
fix: correct sector allocation rounding
docs: update broker-integrations.md with Groww API pricing
refactor: extract holdings normalization into shared util
chore: bump SQLAlchemy version
```

## Testing Strategy

- **Backend:** pytest — unit tests for services (especially normalization logic in broker adapters, and health-metric calculations), integration tests for API endpoints against a test database. **Start `docker compose up -d` first**: the suite exercises the real Redis-backed refresh-token and rate-limit paths, and without Redis 61 tests fail as `TypeError: 'NoneType' object is not subscriptable` — which reads as application bugs rather than a missing dependency.
- **Frontend:** Vitest/Jest for component and hook logic.
- **E2E:** Playwright, reserved for the critical paths only (register → connect broker → view profile) — added once Phase 1 is stable enough for E2E tests to be worth the maintenance cost, not from day one.
- Broker adapters should be testable against recorded/mocked API responses, not live broker accounts, so tests don't depend on real credentials or real market state.

## Deployment Workflow

- **Frontend:** Vercel, auto-deploy on push to `main`, preview deployments per PR.
- **Backend + workers:** Railway (or AWS if scale later demands it), with a migration-run step in the deploy pipeline before the new app version receives traffic.
- **Environments:** local → staging → production, with staging used specifically for testing broker-integration flows against sandbox credentials where available (Upstox provides a sandbox; not every broker does — see [broker-integrations.md](./broker-integrations.md)).
