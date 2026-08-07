# Operational Gotchas

**Last verified: 2026-08-04**

**Purpose:** the traps in this repository that have actually cost time — each
one either observed directly or reproduced during an audit. This document owns
workflow pitfalls. It does not own known debt
([TECHNICAL_DEBT.md](./TECHNICAL_DEBT.md)), setup instructions
([development-guide.md](./development-guide.md)), or runbooks
([operations.md](./operations.md)).

Every entry answers three questions: **what goes wrong**, **why**, and **what to
do instead**. Nothing here is hypothetical. If a trap stops being real, delete
it — a list of things that used to be true is a list nobody reads.

---

## Git & repository

### `apps/web` is a git submodule

**What goes wrong.** You edit a frontend file, commit in the project root, push,
and the change doesn't exist for anyone else. Or you clone the repo and
`apps/web` is an empty directory.

**Why.** `apps/web` points at a separate repository,
`ChandanSurya96/nexarch-web`. This repository stores a **commit pointer**, not
the frontend's files. A parent-repo commit records "the submodule is at hash X".

**Do instead.**

```bash
git clone --recurse-submodules <repo-url> nexarch
```

Already cloned without it:

```bash
git submodule update --init --recursive
```

A frontend change is **two commits and two pushes**, in this order:

1. `cd apps/web`, commit, **push**. The push is not optional — the parent will
   point at a commit nobody else can fetch, and CI's submodule checkout fails.
2. `cd ../..`, commit the pointer bump, push.

If the submodule commit is on a branch, the parent's pointer targets that
branch. Merge the frontend PR before merging the parent if you want the pointer
to track `main`.

### Local `main` can be behind `origin/main`

**What goes wrong.** You branch off `main`, and your branch silently lacks
recent merged work — as of 2026-08-04 local `main` was **4 commits behind**,
missing the CI runner migration.

**Do instead.** `git fetch && git checkout main && git pull` before branching.
`git log --oneline main..origin/main` shows exactly what you're missing.

### `git show origin/main:path` fails in Git Bash on Windows

**What goes wrong.**

```
fatal: ambiguous argument 'origin\main;.github\workflows\ci.yml':
unknown revision or path not in the working tree
```

**Why.** Git Bash's path translation mangles the `rev:path` colon syntax.

**Do instead.** Use PowerShell with the whole argument quoted:

```powershell
git show "origin/main:.github/workflows/ci.yml"
```

---

## Formatting — both of these have reformatted large parts of this repo

### Run `black` and `ruff` from `apps/api`, with paths inside it

**What goes wrong.** `black` silently reformats **68 files** at line-length 88
instead of the configured 100, and re-running at 100 does **not** undo it.

**Why.** Black resolves its config from the common parent of the paths you give
it. `apps/api/pyproject.toml` sets `line-length = 100`; the repository root has
**no `pyproject.toml`** (verified). So passing a path outside `apps/api` — for
example `../../scripts/` — moves the config root to the repository root, where
Black finds no config and falls back to its default of 88. The round trip is
lossy because of the magic trailing comma, so the only fix is `git checkout` of
every unintended file.

**Do instead.** Always from `apps/api`, always with paths inside it:

```bash
black app/
```

Never `black ../../scripts/` or `black .` from the repository root.

### There is no Prettier in this project

**What goes wrong.** `npx prettier --write .` reformats the frontend at its own
80-column defaults. It happened once and had to be reverted across 26 files.

**Why.** Prettier is **not a dependency** and there is **no Prettier config**
anywhere in `apps/web` (verified against `package.json` and the filesystem).
`npx` downloads it on demand and, finding no config, applies its own defaults —
which are not this codebase's.

**Do instead.** `npm run lint`. ESLint via `next lint` is the frontend's
formatter of record. If you genuinely want Prettier, that's a dependency and a
config file, decided deliberately — not an ad-hoc `npx` invocation.

---

## Running the backend

### The test suite needs Postgres and Redis running

**What goes wrong.** **61 of 326 tests fail** with
`TypeError: 'NoneType' object is not subscriptable` — which reads as 61 real
application bugs. The actual cause is several frames down:
`redis.exceptions.TimeoutError: Timeout connecting to server`.

**Why.** Tests exercise the real refresh-token and rate-limit paths, which are
genuinely Redis-backed. A login that can't write its token family returns an
error body, and the test subscripts `resp.get_json()["data"]` on `None`.

**Do instead.**

```bash
docker compose up -d
```

Verified both ways on 2026-08-04: Docker down → 61 failures; Docker up →
**326 passed**. If you see a wave of `NoneType` errors, check Docker before
reading a single line of application code.

### The test suite needs `apps/api/.env`

**What goes wrong.** pytest aborts **during collection**, before running
anything:

```
sqlalchemy.exc.ArgumentError: Could not parse SQLAlchemy URL from string ''
ERROR tests/test_sync_monitoring.py
ERROR tests/test_sync_tasks.py
Interrupted: 2 errors during collection
```

**Why.** Those two modules build a Celery/SQLAlchemy context at import time,
which needs `DATABASE_URL`. `.env` is gitignored, so a fresh clone or a new
worktree has no `.env` and therefore no `DATABASE_URL`.

**Do instead.** `cp .env.example .env` and fill in local values. Note the
failure mode is a **hard collection abort**, not a set of individual test
failures — zero tests run, so a green-looking "no failures" is impossible to
misread here, but the SQLAlchemy error points at the database rather than at the
missing file.

### Use the venv interpreter directly

**What goes wrong.** `source venv/Scripts/activate` has silently failed to
switch interpreters on this machine, so commands run against system Python —
which has a different, often stale, package set. The symptom is an
`ImportError` for a package you know is installed.

**Do instead.** Call the interpreter by path, which cannot be ambiguous:

```bash
./venv/Scripts/python.exe -m pytest
./venv/Scripts/python.exe -m ruff check app/
./venv/Scripts/python.exe -m black app/
```

---

## Running the frontend

### Never run `npm run build` while `npm run dev` is running

**What goes wrong.** The dev server starts 500ing with
`Cannot find module './42.js'` on a route that worked seconds earlier.

**Why.** `next dev` and `next build` share the `.next` directory. The build
overwrites the chunks the dev server is actively serving.

**Do instead.** Stop the dev server, delete `.next`, then build. Same in
reverse when switching back to dev.

---

## Frontend styling & motion

### Landing styles are scoped to `.landing` and don't leak

**What goes wrong.** You add a product token (`--text-tertiary`, say) expecting
it to apply on the landing page, or you change an `--l-*` token expecting it to
affect the product UI. Neither happens.

**Why.** Deliberate (ADR-049). The landing page renders inside a `.landing`
wrapper whose `--l-*` tokens live in `styles/landing.css`; the product's tokens
live in `styles/globals.css`. They're independent by design, because the two are
different visual registers and merging them re-creates the drift the design
system removed.

**Do instead.** Know which side you're on. `--l-*` = landing only. Everything
else = product only. A `--text-tertiary` and an `--l-text-3` can mean similar
things and hold different values; that's expected.

### `motion.*` throws on the landing page — use `m.*`

**What goes wrong.** Adding a `<motion.div>` under `components/landing/` throws
at runtime.

**Why.** Deliberate (ADR-050). The page wraps itself in
`<LazyMotion features={domAnimation} strict>`, which ships roughly a fifth of
Framer Motion's bundle. `strict` makes `motion.*` throw rather than silently
pulling in the full feature set — a loud failure instead of a quiet 34 kB
regression.

**Do instead.** `import { m } from "framer-motion"` and use `m.div`. Note that
`m` is imported in most landing modules, so **don't name a local variable `m`**
— it shadows the component. `IdentityCard.tsx` carries a comment marking the one
place a `.map` callback was deliberately not named `m`.

### Measure contrast in the DOM, not with arithmetic on tokens

**What goes wrong.** A colour computed to pass WCAG AA measures below it in the
browser. This has produced a wrong answer **twice**: a value estimated at 4.6:1
measured 4.09:1, and a corrected token was validated against only two of the
four surfaces it actually renders on.

**Why.** Tokens carry alpha, and the effective background is the composite of
the whole ancestor stack. A sweep that ignores alpha also produces `ratio: 1`
false positives by comparing an element against itself.

**Do instead.** Sweep computed styles in the live page, compositing alpha up the
full ancestor chain. Every pair needs ≥ 4.5:1 (3:1 for large text and non-text).

---

## Database & migrations

### A new Postgres ENUM value needs its own migration — and SQLite won't tell you

**What goes wrong.** A code path writes an enum value that exists in the Python
enum but not in the Postgres type. Every request down that path returns **500 in
production**, after the row has already committed. The local test suite is
perfectly green.

**Why.** SQLite doesn't enforce enums, so a missing `ALTER TYPE` is invisible to
a SQLite-backed suite. This shipped twice: migration `0006` added `logout` and
`reuse`, and `reconnect` was still missing from `audit_event_type_enum` from
Milestone 2 until CI's first run against **real Postgres** caught it — three
hardening slices later. Broker reconnects are routine, so this was a live 500 on
a common path.

**Do instead.** Adding an enum value means a migration:

```python
op.execute("ALTER TYPE audit_event_type_enum ADD VALUE IF NOT EXISTS 'reconnect'")
```

`tests/test_audit_log_enum.py` now parses every `log_event` call site against
the migration-defined values and fails on SQLite in under a second. It handles
the ternary form (`"connect" if is_new else "reconnect"`), which is exactly how
`reconnect` hid. Don't defeat it by constructing an event type dynamically.

---

## CI & deployment

### CI is currently not running

Every run since 2026-08-02 has sat queued until cancelled, under both runner
labels. A PR without a green check is not evidence of a code problem right now.
Full detail and evidence in [CURRENT_STATE.md](./CURRENT_STATE.md).

**Do instead.** Run the checks locally before claiming anything passes:

```bash
docker compose up -d
```

then `pytest`, `ruff check app/`, `black --check app/` in `apps/api`, and
`npm run lint`, `npm run type-check`, `npm test`, `npm run build` in `apps/web`.

### Point Vercel at `nexarch-web`, not at this repository

**What goes wrong.** Connecting Vercel to `Nexarch-project` deploys a repository
whose `apps/web` is a submodule pointer, not a Next.js app.

**Do instead.** Connect Vercel to `ChandanSurya96/nexarch-web`. Railway takes
this repository, for the API and workers.

### Production refuses to boot on unsafe configuration — on purpose

**What goes wrong.** A production deploy exits at startup complaining about
`JWT_SECRET` or `ENCRYPTION_KMS_KEY_ID`.

**Why.** Deliberate (ADR-039). `create_app("production")` previously started
cleanly with an empty `JWT_SECRET` and issued JWTs signed with the empty string
— forgeable for any user id, with `/health` reporting green throughout. Config
validation now refuses to boot when secrets are missing, empty, placeholders, or
under 32 characters, or when `DATABASE_URL`/`REDIS_URL` are unset or localhost.

**Do instead.** Set them properly. This is the system working. Dev and test
environments are unaffected.
