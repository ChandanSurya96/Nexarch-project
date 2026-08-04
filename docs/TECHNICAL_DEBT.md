# Technical Debt

**Last verified: 2026-08-04**

**Purpose:** the known, *verified* engineering debt in this repository — what it
is, why it exists, what it costs, and what fixing it looks like. This document
owns known debt. It does not own future features ([roadmap.md](./roadmap.md)),
current status ([CURRENT_STATE.md](./CURRENT_STATE.md)), or workflow traps
([OPERATIONAL_GOTCHAS.md](./OPERATIONAL_GOTCHAS.md)).

**Every item below was confirmed against the code on the date above.** Nothing
here is inferred from a previous document or from a plausible-sounding worry. If
you find something that belongs here, verify it first, then add it with the
evidence — a file and line, a measurement, or a reproduction.

**Priorities**

| | Meaning |
|---|---|
| **P1** | Fix before real users. A user or an on-call engineer feels this |
| **P2** | Fix soon after beta. Real, not urgent |
| **P3** | Fix when the area is next touched. Cosmetic, or bounded by current scale |

---

## Backend

### B1 · A Redis outage returns 500 from every non-health route — **P1**

**What.** `flask-limiter` is initialised with `default_limits=["100 per minute"]`
([`app/extensions.py:38`](../apps/api/app/extensions.py)), which applies to every
route, and `RATELIMIT_STORAGE_URI` is Redis outside tests
([`app/config.py:109`](../apps/api/app/config.py)). The limiter counts hits in
`before_request`, ahead of any route code, so when Redis is unreachable it raises
before the endpoint runs. Only `health_bp` is exempt
([`app/routes/health.py:30`](../apps/api/app/routes/health.py)).

**Why it exists.** ADR-034 found this exact failure on `/health` during its own
verification and fixed it *there*, with a blueprint-level exemption. The general
case — every other route — was never addressed. The same shape recurred twice
more and was fixed pointwise both times: `/health` (ADR-034) and the discovery
feed (ADR-045). This is the third instance of one pattern.

**Impact.** Redis is a cache, a queue, a rate-limit store and a refresh-token
store here. A Redis blip currently escalates from "caching degrades" to "the API
is down", including endpoints that need no Redis at all. `/health` stays green
throughout, so the load balancer keeps routing traffic to instances that 500 —
which is the worst combination.

**Suggested fix.** Make limiter storage failure fail *open*: either a
`flask-limiter` storage wrapper that swallows connection errors and permits the
request, or catch the error in an app-level `before_request` guard. Failing open
loses rate limiting during an outage — the correct trade, since the alternative
is a total outage, but it should be logged loudly and stated in
[security.md](./security.md). Add a test that patches the storage to raise and
asserts a normal 200.

### B2 · One broker adapter is deployable — **P1 (needs a founder decision)**

**What.** `app/integrations/broker/` contains `base.py`, `registry.py` and
`upstox.py`. The registry registers `upstox` alone. The Dhan adapter exists as
commit `81f5e20` on the local branch `feature/milestone-8-dhan-broker`, which is
**not merged and not pushed to origin**.

**Why it exists.** Milestone 8 was built in a working session that also produced
a Phase 2.5 slice; the Dhan work was left on its own branch to keep the slices
separate, and was never pushed. [changelog.md](./changelog.md) recorded this
accurately; the status summary in `docs/README.md` did not, and claimed Phase 2
included "the Dhan integration". Corrected 2026-08-04.

**Impact.** Two-fold. Product: Nexarch supports exactly one broker in any
deployable state, which materially narrows who can be invited to a beta.
Engineering: the work exists on **one machine, unpushed** — a disk failure loses
it, and it drifts further from `main` every week.

**Suggested fix.** Push the branch today regardless of the merge decision — that
part is free and removes the single point of failure. Then either open a PR and
merge it, or formally move Dhan to future work in [roadmap.md](./roadmap.md).
The current in-between state is the only bad option.

### B3 · `ENCRYPTION_KMS_KEY_ID` is a stand-in, not a KMS — **P2**

**What.** Broker token encryption uses envelope encryption with a master key
supplied as an environment variable. ADR-044 made it versioned and rotatable
with zero user reconnects, verified end to end.

**Why it exists.** ADR-014 chose an env-var master key deliberately, to avoid a
cloud-provider dependency before a hosting decision existed. ADR-044 notes
explicitly that making the stand-in rotatable does not make it a KMS.

**Impact.** The master key is readable by anything that can read the process
environment, and there is no hardware-backed custody or per-use audit trail.
Acceptable for a closed beta; not the story to tell during a security review.

**Suggested fix.** Move to a real KMS once the hosting platform is chosen. The
versioned format was designed for this — the migration is a re-wrap pass
(`scripts/rewrap_encryption_keys.py`), not a schema change.

### B4 · The backend suite requires live Postgres and Redis, and fails opaquely without them — **P3**

**What.** With Docker down, 61 of 326 tests fail with
`TypeError: 'NoneType' object is not subscriptable` — a Redis connection timeout
surfacing as an application-shaped error several frames from its cause.
Verified 2026-08-04, both ways.

**Why it exists.** Tests exercise the real refresh-token and rate-limit paths,
which are genuinely Redis-backed. That's the right call — the alternative is
mocking the dependency whose failure modes have caused three separate production
bugs here.

**Impact.** Purely developer time, but sharply: the failure looks like 61 real
application bugs. This has already cost one debugging detour.

**Suggested fix.** A `conftest.py` session fixture that pings Redis and Postgres
once and fails with `docker compose up -d` in the message. One fixture, and the
class of confusion disappears.

---

## Frontend

### F1 · Three landing components exceed the 150-line limit the brief set — **P3**

**What.** `Hero.tsx` (210), `Fingerprint.tsx` (176), `ScreenshotChain.tsx` (158).
Every other landing component is under. Verified by line count 2026-08-04.

**Why it exists.** `Hero.tsx` carries two local sub-components plus two layered
backgrounds; `Fingerprint.tsx` holds the ring-geometry maths, which is cohesive
and arguably belongs in one place.

**Impact.** Low. These are leaf components with no shared state.

**Suggested fix.** Extract `Enter` and `FloatingCard` from `Hero.tsx` into
`Primitives.tsx`; move `computeRingPath` out of `Fingerprint.tsx` into a
`lib/fingerprint.ts` that can be unit-tested independently of React. Do it when
the page is next touched, not as its own task.

### F2 · Frontend test coverage is thin relative to the backend — **P2**

**What.** 42 tests across 12 files, against 326 backend tests. Verified by
running both 2026-08-04.

**Why it exists.** The frontend was built route-first through Phase 1, then
rebuilt onto the design system in one slice. Neither pass was test-driven.

**Impact.** The design-system migration touched every route, and its correctness
rests on lint, typecheck, a production build and manual verification at four
breakpoints. Those catch compile errors and layout regressions; they don't catch
a metric rendering the wrong field.

**Suggested fix.** Cover the primitives first (`Metric`, `Surface`,
`PortfolioIdentityStrip`) since every page depends on them — particularly the
strip's render-`null`-when-empty contract, which is a correctness rule, not
styling. Then the data-shaping in `lib/format.ts`.

### F3 · The Portfolio Identity Strip's `tiny` variant is unused — **P2, blocked on the backend**

**What.** The `tiny` variant exists for discovery and library cards. It renders
nowhere, because `GET /discovery/investors` and `GET /public-investors` don't
return `sector_allocation`.

**Why it exists.** The strip renders `null` rather than inventing an allocation
(ADR-048), which is correct — but it means the highest-value placement is dark.

**Impact.** The grids that would most benefit from a scannable portfolio shape
don't have one. A discovery feed you scan by shape is the product's core
differentiator, and it currently reads as a list of names.

**Suggested fix.** Add `sector_allocation` to both list serialisers. The data is
already computed and stored — this is a serialiser change, not new analytics.
See the field table in [design-system.md](./design-system.md).

### F4 · Seeded library portfolios have no analytics at all — **P2, blocked on the backend**

**What.** All five Public Investor Library portfolios return
`sector_allocation: {}` and `health: null`, because analytics are computed during
`run_sync` and seeded portfolios never sync.

**Why it exists.** The seed script writes holdings directly; analytics were only
ever wired into the sync path.

**Impact.** No library profile shows health metrics, an allocation chart, or the
identity strip — despite their holdings carrying real sector data. The Public
Investor Library exists to solve cold start, so it is precisely the surface a
first-time visitor judges, and it is the emptiest.

**Suggested fix.** Extract analytics computation out of `run_sync` and call it
from the seed script too. The service split already exists; it's the call site
that's missing.

### F5 · Discovery filters are component state, not URL state — **P3**

**What.** Strategy, sort and page live in `useState`
([`app/discover/page.tsx:26-28`](../apps/web/app/discover/page.tsx)).

**Impact.** A filtered view can't be shared or deep-linked, and the back button
doesn't step through filter changes. On a discovery product, "send someone this
view" is a natural thing to want.

**Suggested fix.** Move to `useSearchParams` + `router.replace`.

### F6 · `Avatar`'s `<img>` has no explicit dimensions — **P3**

**What.** [`components/ui/Avatar.tsx:32`](../apps/web/components/ui/Avatar.tsx)
renders a bare `<img>` with no `width`/`height`.

**Impact.** Layout shift as a remote avatar loads. Initials-only avatars — the
current default everywhere — are unaffected, so this is latent rather than live.

**Suggested fix.** Set explicit dimensions from the size variant.

### F7 · The holdings table is not virtualised — **P3**

**Impact.** None at current volumes. A portfolio past ~50 positions would want it.

---

## Infrastructure

### I1 · CI has not produced a passing run since 2026-07-31 — **P1 (needs a founder decision)**

Fully documented in [CURRENT_STATE.md](./CURRENT_STATE.md) under Known Blockers,
including the run-by-run evidence. Summarised here so this document is complete:
every run since the Blacksmith runner migration has sat queued until cancelled,
under *both* runner labels, which points at something account-level that can only
be inspected from the GitHub account.

**Impact.** The guarantee Phase 2.5 Slice 4 was built to establish — that `main`
is always verified against real Postgres and Redis — is not currently in force.
Notably, CI's *first* run against real Postgres is what caught the latent
`reconnect` enum bug that three slices of SQLite-only testing had hidden. That
safety net is currently down.

### I2 · The deploy workflow has never executed — **P1, blocked on provisioning**

`.github/workflows/deploy.yml` is written, gated behind a typed confirmation, and
runs migrations before traffic cutover. It has never run, because the Railway
project doesn't exist. A runbook step nobody has run is exactly the failure mode
Phase 2.5 existed to eliminate.

### I3 · `infra/` is empty — **P3**

Contains only `.gitkeep`. Deployment configuration lives in
`.github/workflows/` and `apps/api/Dockerfile` instead. Not a problem — but the
directory implies a home for infrastructure-as-code that nothing uses, and
[development-guide.md](./development-guide.md) describes it as "deployment
configs". Either populate it or remove it; an empty labelled drawer sends people
looking.

---

## Documentation

### D1 · Four items need founder decisions before they can be resolved — **P1**

Not debt that engineering can pay down. Listed in full at the end of this
document.

### D2 · Docs record decisions the implementation deliberately deferred — **P3**

Several documents describe intended end states alongside what exists — the
`.env.example` lists API keys for five brokers of which one is implemented, and
`architecture.md` diagrams six broker integrations. This is *intentional*
(the architecture is designed to make adding them additive), but it reads as
"already built" on a fast skim, which is how `docs/README.md` came to claim a
Dhan integration that isn't on `main`.

**Suggested fix.** No sweeping rewrite. When a doc names a broker, say whether
it's implemented. The `Last verified` blocks added 2026-08-04 make the check
routine rather than heroic.

---

## Product

### PR1 · The broker data-vending question is still open — **P1 (needs a founder decision)**

**What.** Displaying synced holdings publicly may conflict with at least one
broker's terms — Zerodha's Kite Connect terms describe it as an execution
platform, not a data-redistribution service. Recorded as ADR-011 and still
unresolved.

**Why it matters now.** New broker connections default `is_public = false`
precisely because of this, and that default is a non-negotiable rule until the
question is answered. A public investor library whose verified profiles are all
private by default is a product with its core loop gated on a legal answer
nobody has yet.

**Suggested fix.** A direct conversation with each broker before public profiles
go live. Not an engineering task.

### PR2 · The landing page names brokers Nexarch doesn't integrate — **P1 before the page is public**

**What.** The broker-flow section lists "Zerodha, Groww, Upstox, or Angel One"
([`components/landing/BrokerFlowSection.tsx:10`](../apps/web/components/landing/BrokerFlowSection.tsx)).
Only Upstox is implemented on `main`.

**Why it exists.** The copy came from the Figma source. A related instance — a
"BROKER VERIFIED" line naming Zerodha — was corrected during the recreation
(ADR-049), but this one was flagged rather than fixed, because unlike a
verification claim it reads as a roadmap statement.

**Impact.** On a product whose entire premise is verified, non-self-reported
data, a landing page overstating which brokers connect is the worst possible
place to be loose. It is also the first thing a beta invitee reads.

**Suggested fix.** Name only what's implemented, or mark the others as coming
soon. One line of copy; needs a founder call on which.

### PR3 · "Watchlists" is listed in Phase 2 but was never built — **P3**

**What.** [roadmap.md](./roadmap.md) lists "Watchlists (follow without needing an
account relationship)" under Phase 2. There is no watchlist code
(`grep -r watchlist apps/api/app` returns nothing). Follows exist and shipped in
Phase 1 (`follow_service.py`, `POST/DELETE /portfolios/:id/follow`).

**Why it exists.** Phase 2's goal was "discovery becomes genuinely useful", and
the milestones that delivered it (Health Metrics, Comparison, Strategy
Categorization) met that goal without watchlists. The phase was closed on its
goal, correctly per the roadmap's own "a phase is done when its goal is
demonstrably true" rule — but the unbuilt item was never marked.

**Impact.** Minimal in practice; follows cover most of the need. Recorded so it
isn't rediscovered as a regression.

**Suggested fix.** Decide whether watchlists are meaningfully different from
follows. If not, strike the line. Marked as not-built in `roadmap.md`
2026-08-04 either way.

---

## Requires a founder decision

Engineering cannot close these. They are listed here so they stay visible rather
than accumulating silently.

| # | Decision | Blocking |
|---|---|---|
| 1 | **Why is CI queueing indefinitely?** Needs the GitHub account — runner provisioning, billing, or Actions quota | Merging anything on a green check (I1) |
| 2 | **Dhan: merge or defer?** The branch is unpushed and unmerged | Beta broker coverage (B2) |
| 3 | **Broker data-vending (ADR-011)** — may public profiles show synced holdings? | The public investor library's core loop (Product PR1) |
| 4 | **Landing-page broker copy** — name only Upstox, or mark the rest "coming soon"? | Making the landing page public (Product PR2) |

Two further items are *blocked on provisioning* rather than on a decision: the
deployment rehearsal and the first real deploy. Both are the founder's to unblock
by creating accounts and holding secrets; every config, workflow, script and
runbook that consumes them is written and waiting.
