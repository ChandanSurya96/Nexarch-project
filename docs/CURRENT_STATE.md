# Current State

**Last verified: 2026-08-04**

**Purpose:** the canonical snapshot of what this repository *is today* — stage,
status, blockers, priorities. Everything here is volatile by design and should
be re-verified rather than trusted after its date above.

This document owns **today**. It does not own architecture ([architecture.md](./architecture.md)),
future work ([roadmap.md](./roadmap.md)), reasoning ([decisions.md](./decisions.md)),
or history ([changelog.md](./changelog.md)). If you find long-term design
rationale here, it's in the wrong file.

**Every figure below was measured against the repository on the date above**, not
carried forward from a previous entry.

---

## At a glance

| | |
|---|---|
| **Project stage** | **Beta Candidate** |
| **Current phase** | None in progress — Phase 2.5 closed, engineering deliberately stopped |
| **Last completed work** | Demo-completion polish, batches 1–3 (UX, accessibility, validation copy) |
| **Current branch** | `feature/design-system-and-landing-page` |
| **Open PRs** | [#13](https://github.com/ChandanSurya96/Nexarch-project/pull/13) — design system + landing page. `MERGEABLE`, CI did not run (see Blockers) |
| **Latest merged work** | PR #12 — Blacksmith CI runner migration (2026-08-02), on `origin/main` |
| **Blocking beta** | Infrastructure provisioning and a working CI pipeline — both need the founder |
| **Next engineering work** | **None recommended.** See "Why no new engineering" below |

---

## Project maturity

```
Backend          █████████░  95%
Frontend         ████████░░  85%
Infrastructure   ██████░░░░  60%
Deployment       ██░░░░░░░░  25%
Documentation    █████████░  95%
Launch readiness ██████░░░░  65%
```

**How these were derived** — so they can be argued with rather than inherited:

- **Backend 95%** — 334 tests pass, lint and format clean, five hardening slices
  done. Short of 100% because exactly **one** broker adapter (Upstox) is on
  `main`; the Dhan adapter exists only on an unpushed local branch (see Blockers).
- **Frontend 85%** — every route composes from the design system, the landing
  page ships, 45 tests pass. Held down by thin test coverage relative to the
  backend, and the UI debt in [TECHNICAL_DEBT.md](./TECHNICAL_DEBT.md).
- **Infrastructure 60%** — `docker compose` works locally and CI is fully
  written, but **CI has not produced a passing run since 2026-07-31**, and
  `infra/` contains nothing but a `.gitkeep`.
- **Deployment 25%** — every workflow, Dockerfile, script and runbook exists;
  none has ever run against real infrastructure, because none exists.
- **Documentation 95%** — comprehensive and now audited end to end. The
  remaining 5% is items needing founder decisions, listed below.
- **Launch readiness 65%** — the product is built; the path to users isn't open.

---

## Backend status

**Complete and verified.** `apps/api`, in this repository.

| | |
|---|---|
| Tests | **334 passing**, 0 failing (`pytest`) |
| Lint | `ruff check app/` — clean |
| Format | `black --check app/` — clean, 67 files |
| Migrations | 8 (`0001` → `0008`), Alembic |
| Blueprints | 7 — auth, users, broker-connections, portfolios, discovery, public-investors, health |
| Services | 19 under `app/services/` |
| Models | 9 under `app/models/` |
| Broker adapters | **1 — Upstox only** |
| Health endpoints | `/health`, `/health/ready`, `/health/sync` |

**The test suite requires a live Postgres and Redis.** Without them, 61 tests
fail with `TypeError: 'NoneType' object is not subscriptable` — a Redis
connection timeout surfacing as an application-shaped error. Run
`docker compose up -d` first. See [OPERATIONAL_GOTCHAS.md](./OPERATIONAL_GOTCHAS.md).

## Frontend status

**Complete for beta.** `apps/web` — a **git submodule** (`ChandanSurya96/nexarch-web`),
not files in this repository.

| | |
|---|---|
| Tests | **45 passing** across 13 files (`vitest`) |
| Routes | 9 — `/`, `/login`, `/register`, `/broker-callback`, `/discover`, `/library`, `/compare`, `/profile`, `/portfolios/[id]` |
| Design system | Every route composes from `components/ui` (ADR-048) |
| Landing page | `/`, recreated from Figma, tokens scoped to `.landing` (ADR-049) |
| Motion | Framer Motion via `LazyMotion` + `m`, landing route only (ADR-050) |

## Infrastructure status

| | |
|---|---|
| Local dev | `docker compose up -d` — Postgres 15 + Redis 7. Working |
| CI | `.github/workflows/ci.yml` — **currently not running.** See Blockers |
| Deploy workflow | `.github/workflows/deploy.yml` — written, **never executed** |
| Container image | `apps/api/Dockerfile` — one image for API and worker |
| `infra/` | Empty (`.gitkeep` only) — deployment config lives in the workflows |

## Deployment status

**Nothing is deployed. There is no production environment.**

| Component | Target platform | Status |
|---|---|---|
| API / worker / beat | Railway | **Not provisioned** |
| Frontend | Vercel | **Not provisioned** — connect it to `nexarch-web`, not this repo |
| Postgres / Redis | Railway managed | **Not provisioned** |
| Error tracking | Sentry | Optional; inert until `SENTRY_DSN` is set |

Everything that consumes these — config validation, deploy workflow, backup and
restore scripts, the runbooks in [operations.md](./operations.md) — is written
and waiting. The gap is provisioning, which requires accounts, payment details
and real secret values that only the founder can create and hold.

---

## Known blockers

Ordered by what stands between here and a beta invite.

### 1. CI has not produced a passing run since 2026-07-31 — **founder action needed**

Verified from the run history:

| Date | Branch | Result |
|---|---|---|
| 2026-07-31 | `feature/phase2.5-slice4-deployment` → `main` | **success**, ~2 min |
| 2026-08-02 | `blacksmith-migration-b2e253e` (PR #11) | cancelled after 24h |
| 2026-08-02 | `blacksmith-migration-3434be4` (PR #12) | cancelled after 24h |
| 2026-08-02 | `feature/design-system-and-landing-page` (PR #13) | cancelled after 10h36m |

Every run since 2026-07-31 sat **queued** until it was cancelled — no job ever
started, so nothing failed on code. `origin/main` now targets
`blacksmith-4vcpu-ubuntu-2404` runners (merged via PRs #11 and #12); PR #13's
branch predates that and still targets `ubuntu-latest`, and it hung too. Since
*both* runner labels hang, the cause is more likely account-level (runner
provisioning, billing, or Actions quota) than the workflow files, but that is
**inference, not verification** — it can only be confirmed from the GitHub
account, which is the founder's.

**Impact:** PR #13 cannot be merged on a green check, and the guarantee Phase
2.5 Slice 4 existed to establish — that `main` is always verified against real
Postgres and Redis — is not currently in force.

**This does not indicate a code problem.** The full suite passes locally: 334
backend tests and 45 frontend tests, verified today.

### 2. Local `main` is 4 commits behind `origin/main`

`origin/main` carries the Blacksmith runner migration; the local checkout
doesn't. Anything branched from local `main` starts without it. PR #13 does not
touch `.github/workflows/`, so merging it will **not** revert the migration —
verified. Run `git fetch && git checkout main && git pull` before branching.

### 3. The Dhan broker integration is not on `main`

`docs/README.md` described Phase 2 as including "the Dhan integration". Verified
against the repository: **there is no Dhan adapter on `main`.**
`app/integrations/broker/` contains `base.py`, `registry.py` and `upstox.py`,
and the registry registers `upstox` alone. The work exists as commit `81f5e20`
on the local branch `feature/milestone-8-dhan-broker`, which is **not merged and
not pushed to origin** — so it exists on exactly one machine and is one disk
failure from gone. [changelog.md](./changelog.md) recorded this correctly at the
time; the status summary did not, and has been corrected.

**Impact:** Nexarch supports one broker in any deployable state. **Founder
decision needed:** push and merge that branch, or formally move Dhan back to
future work.

### 4. Deployment rehearsal — blocked, not skipped

Migrations, Docker startup, graceful shutdown and the backup/restore drill have
all been exercised locally. An actual deploy cannot be rehearsed against
infrastructure that doesn't exist, and a runbook step nobody has run is exactly
what Phase 2.5 existed to eliminate. Unblocked by provisioning, not by code.

---

## Current priorities

Operational, in order. None of these is an engineering task.

1. **Restore CI.** Nothing else should merge until a run goes green.
2. **Decide the Dhan question** — push and merge, or defer explicitly.
3. **Merge PR #13** once CI is green.
4. **Provision Railway and Vercel** (and Sentry, if error tracking is wanted
   from day one). Point Vercel at `ChandanSurya96/nexarch-web`.
5. **First real deployment**, following [operations.md](./operations.md).
6. **Execute the production checklist**, including the deployment rehearsal that
   is currently blocked.
7. **Invite a handful of trusted beta users.**
8. **Collect real feedback before building anything else.**

## Next recommended engineering work

**None.** This is a deliberate position, not an oversight.

Phase 2.5 closed with the project at Beta Candidate on the explicit reasoning
that what remains is operational rather than architectural. Opening another
slice now would add unvalidated surface area to a product no real user has ever
touched — and every remaining known issue is either recorded in
[TECHNICAL_DEBT.md](./TECHNICAL_DEBT.md) with a priority, or blocked on
infrastructure that doesn't exist yet.

If something must be done, take it from `TECHNICAL_DEBT.md` in priority order —
don't invent a new slice. Nothing from Phase 2+ (execution, copy trading,
subscriptions, notifications, chat, community posts) gets built unless
explicitly asked.

---

## Test, lint and CI status

| Check | Where | Status | Verified |
|---|---|---|---|
| Backend tests | `apps/api` — `pytest` | **334 passed** | 2026-08-04 |
| Backend lint | `ruff check app/` | clean | 2026-08-04 |
| Backend format | `black --check app/` | clean, 67 files | 2026-08-04 |
| Frontend tests | `apps/web` — `npm test` | **45 passed**, 13 files | 2026-08-04 |
| Frontend lint | `npm run lint` | clean | 2026-08-03 |
| Frontend types | `npm run type-check` | clean | 2026-08-03 |
| Frontend build | `npm run build` | succeeds, shared JS 106 kB | 2026-08-04 |
| **CI pipeline** | GitHub Actions | **not running — see Blockers** | 2026-08-04 |

Backend tests require `docker compose up -d` first.

## Production readiness

| Requirement | Status |
|---|---|
| Production refuses to boot on unsafe config | Done (ADR-039) |
| Secrets never in the repository | Done — `.env.example` placeholders only |
| Encryption key rotatable without user reconnects | Done, executed end to end (ADR-044) |
| Login timing does not leak account existence | Done — 122x → 1.08x (measured) |
| Structured logging with request-id correlation | Done (ADR-034) |
| Liveness / readiness / sync-pipeline probes | Done (ADR-034, ADR-047) |
| Backup and restore | Scripts written, restore drill executed |
| Rate limiting, CSRF, refresh-token rotation | Done (ADR-029–033) |
| CI enforcing the above on every PR | **Written, not currently running** |
| Deployed environment | **Does not exist** |
| Deployment rehearsal | **Blocked on the above** |
| Error tracking wired | Done, inert until `SENTRY_DSN` set (ADR-041) |

## Launch checklist progress

- [x] Phase 1 — Foundation & MVP
- [x] Phase 2 — Analytics & Comparisons *(except: Dhan not on `main`; Watchlists never built)*
- [x] Phase 2.5 — Production Hardening, all five slices
- [x] Frontend — design system + marketing landing page
- [x] Documentation audited against the implementation
- [ ] **CI restored to a passing state**
- [ ] Open PRs merged
- [ ] Railway provisioned
- [ ] Vercel provisioned (→ `nexarch-web`)
- [ ] First real deployment
- [ ] Production checklist in [operations.md](./operations.md) executed
- [ ] Deployment rehearsal completed
- [ ] Beta users invited
- [ ] Real feedback collected

---

## Starting a new session

Read in this order. It goes from *volatile* to *stable*, so you get today's
reality before absorbing long-term structure — the opposite order leads to
confidently acting on a plan that has already moved.

| # | Document | Why here |
|---|---|---|
| 1 | **CURRENT_STATE.md** (this file) | What is true *today*. Everything else describes intent; this describes the repository. Read it first so you never open a "next milestone" that was deliberately closed |
| 2 | **[CLAUDE.md](../CLAUDE.md)** | How to work here — rules, conventions, commands, and the non-negotiables. Loaded automatically, but read it deliberately: several rules exist because breaking them cost real rework |
| 3 | **[decisions.md](./decisions.md)** | *Why* the system is shaped as it is, 50 ADRs. Consult before proposing a change — most obvious ideas were considered and rejected here for recorded reasons |
| 4 | **[roadmap.md](./roadmap.md)** | What is deliberately **not** being built, and why. Prevents building something into a phase that hasn't been reached |
| 5 | **[architecture.md](./architecture.md)** | System design and data flow. Last because by this point you know what's real, what's decided, and what's out of scope — so the architecture reads as confirmation, not as instruction |

Then read the doc that owns whatever you're about to touch —
[docs/README.md](./README.md) indexes all of them.

Two more worth knowing before your first change:
[OPERATIONAL_GOTCHAS.md](./OPERATIONAL_GOTCHAS.md) (traps that have cost real
time here) and [TECHNICAL_DEBT.md](./TECHNICAL_DEBT.md) (known debt, so you
don't re-report it as a discovery).

---

## Keeping this document honest

This file's only value is being current. When it drifts it becomes worse than
absent, because it looks authoritative.

- **Update it in the same commit** as anything that changes stage, status,
  blockers, or a test/CI result — not in a follow-up pass.
- **Re-verify, don't copy forward.** Every number here came from running the
  command. Re-run it rather than carrying the old value.
- **Move the date** at the top whenever any claim below it is re-checked.
- **Keep it volatile-only.** Anything still true in six months belongs in the
  document that owns it, linked from here rather than restated.
