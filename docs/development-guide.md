# Development Guide

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
# clone and enter the repo
git clone <repo-url> nexarch && cd nexarch

# start Postgres + Redis
docker compose up -d

# backend
cd apps/api
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in local values
flask db upgrade        # run migrations
flask run

# frontend (separate terminal)
cd apps/web
npm install
cp .env.example .env.local
npm run dev
```

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

## Proposed Project Structure

```
nexarch/
├── apps/
│   ├── web/                        # Next.js frontend
│   │   ├── app/                    # App Router pages
│   │   ├── components/             # Shared UI components (see design-system.md)
│   │   ├── lib/                    # API client, utilities
│   │   ├── hooks/                  # React Query hooks per resource
│   │   ├── styles/
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
└── infra/                          # deployment configs
```

## Coding Standards

- **TypeScript strict mode** on the frontend; no `any` without a comment explaining why.
- **Naming:** camelCase in TS/JS, snake_case in Python — each language's own convention, not forced consistency across the boundary.
- **Functions small and single-purpose.** A service function that does three unrelated things should be three functions.
- **Comments explain *why*, not *what*** — the code should already say what it does.
- **No duplication** — if the same logic appears in a broker adapter and a service twice, it belongs in one shared place.

### Linting & Formatting
- Frontend: ESLint + Prettier, run in CI and as a pre-commit hook.
- Backend: Ruff (lint) + Black (format), same enforcement.

## Git Workflow

- Trunk-based: short-lived feature branches off `main`, merged via PR.
- Branch naming: `feature/<short-description>`, `fix/<short-description>`, `chore/<short-description>`.
- PRs require passing CI (lint, tests) before merge; no direct pushes to `main`.

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

- **Backend:** pytest — unit tests for services (especially normalization logic in broker adapters, and health-metric calculations), integration tests for API endpoints against a test database.
- **Frontend:** Vitest/Jest for component and hook logic.
- **E2E:** Playwright, reserved for the critical paths only (register → connect broker → view profile) — added once Phase 1 is stable enough for E2E tests to be worth the maintenance cost, not from day one.
- Broker adapters should be testable against recorded/mocked API responses, not live broker accounts, so tests don't depend on real credentials or real market state.

## Deployment Workflow

- **Frontend:** Vercel, auto-deploy on push to `main`, preview deployments per PR.
- **Backend + workers:** Railway (or AWS if scale later demands it), with a migration-run step in the deploy pipeline before the new app version receives traffic.
- **Environments:** local → staging → production, with staging used specifically for testing broker-integration flows against sandbox credentials where available (Upstox provides a sandbox; not every broker does — see [broker-integrations.md](./broker-integrations.md)).
