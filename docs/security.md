# Security

**Purpose:** Authentication and authorization architecture, encryption and secrets handling, API security, and the compliance considerations specific to handling financial account data in India. This document should be read before implementing any broker-connection or auth code, not after. See [broker-integrations.md](./broker-integrations.md) for the broker-specific token handling this builds on.

---

## Authentication

- **Passwords:** hashed with bcrypt or argon2. Never stored or logged in plaintext, never included in any error message or audit log payload.
- **Access tokens:** JWT, short-lived (~15 min), sent as `Authorization: Bearer`.
- **Refresh tokens:** longer-lived, stored as httpOnly, secure, SameSite cookies — never in `localStorage` or any JS-accessible storage, so a client-side XSS bug can't exfiltrate a long-lived credential.
- **Rotation:** refresh tokens rotate on use; a reused (already-consumed) refresh token invalidates the whole session family, which catches token theft rather than just tolerating it silently (ADR-030 in [decisions.md](./decisions.md)). A short grace window tolerates the immediately-previous token from a benign concurrent-tab race without treating it as theft — only a token stale by more than one rotation kills the family.

## Authorization

- Users can only read/write their own private data. Public/verified profile data is readable by anyone once the owning user has set `is_public = true` (see [database.md](./database.md)).
- No implicit admin role exists in the MVP schema — internal tooling for support/moderation should use a clearly separate, explicitly audited path once it's needed, not a quiet superuser flag bolted onto the `users` table.

## Broker Token Security

This is the highest-sensitivity data Nexarch holds, and it's treated accordingly:
- Broker access/refresh tokens encrypted at rest (envelope encryption — a data key per record, itself encrypted by a key held in a KMS, not a single static application-wide key).
- Tokens are decrypted only inside the sync worker, at the moment of use, never sent to or exposed in the frontend.
- Tokens scoped read-only wherever the broker's own permission model allows it (see [broker-integrations.md](./broker-integrations.md) for which brokers support this).
- Disconnecting a broker deletes the stored token immediately, not just marks it inactive.

## API Security

- Input validation on every endpoint via the schema layer (see [api.md](./api.md)).
- Rate limiting per-user (authenticated) and per-IP (public endpoints) — see [api.md](./api.md) "Rate Limiting" (ADR-032) for the actual limits shipped.
- **CORS is not configured on the Flask side, and that's the correct state, not a gap.** Browser requests never leave the frontend's own origin: the Next.js app proxies `/api/v1/*` to the real backend server-side (`next.config.ts`'s `rewrites()`, ADR-016), so from the browser's perspective every request is same-origin. There is no cross-origin request for CORS to govern in the first place. A prior version of this doc described "CORS locked to the known frontend origin(s)" as the mitigation, which described a mechanism that was never actually built (no CORS config exists anywhere in `app/__init__.py`) — the real mitigation is the proxy pattern making CORS unnecessary, not a permissive default nobody noticed. If a future consumer needs true cross-origin access (a mobile app, a third-party integration), that will need real CORS configuration (e.g. `flask-cors` with an explicit allow-list) at that time — not before.
- HTTPS enforced everywhere, including local-to-staging traffic between services.
- CSRF protection on cookie-based flows (the refresh-token cookie) — `JWT_COOKIE_CSRF_PROTECT = True` (ADR-031 in [decisions.md](./decisions.md)). In practice this only gates `POST /auth/refresh`, the one endpoint that authenticates via a cookie; the access token always travels via the `Authorization` header, never a cookie, so CSRF never applies to it.
- Every failure path (missing/expired/malformed token, unmatched route, unhandled exception) returns the documented response envelope, not a library's own default error shape (ADR-029 in [decisions.md](./decisions.md); see [api.md](./api.md) for the full error-code table).

## Secrets Management

- All secrets (DB credentials, JWT signing key, broker API keys/secrets, KMS key references) via environment variables, sourced from Vercel/Railway's secret stores — never committed to git.
- `.env.example` documents every required variable name with a placeholder, never a real value (see [development-guide.md](./development-guide.md)).
- **Secret rotation has no written runbook yet** — this doc previously described one as if it existed; it doesn't. There's no production deployment or live cloud secrets manager to rotate against yet, so writing a concrete runbook now would describe a process against infrastructure that doesn't exist. This needs to happen before beta launch, once a real secrets manager is chosen (see [roadmap.md](./roadmap.md) "Deployment" hardening slice) — tracked there, not silently implied as already done here.

## Data Privacy & Compliance (India)

Nexarch handles financial account data, which sits squarely inside India's Digital Personal Data Protection Act, 2023 (DPDP Act) as sensitive personal data. Relevant obligations to build for, not retrofit:
- **Consent:** explicit, specific consent for each category of data processed (holdings, not just "your data" broadly) — this maps naturally onto the broker-connection consent screen, which should say plainly what's being read.
- **Right to erasure:** account deletion should cascade to broker-connection revocation and full data purge, not just a soft-delete flag that leaves synced holdings queryable.
- **Data minimization:** only store what a feature actually uses — the schema in [database.md](./database.md) deliberately doesn't store more than current holdings, allocation, and history, not full transaction-level trade data brokers may also expose.

This document is a starting checklist, not a substitute for actual legal review before launch — DPDP Act compliance, in particular around cross-border data storage if any infrastructure sits outside India, should get dedicated counsel time before Phase 1 ships to real users, not after.

## The Line Between Data and Advice — Why This Is a Security Document Concern, Not Just a Copy Concern

SEBI has been actively enforcing against the "education vs. advice" boundary since 2024, culminating in a December 2025 order impounding roughly ₹546 crore from an academy SEBI found to be running unregistered advisory services under the label of education. The relevant regulations are the SEBI Investment Adviser Regulations, 2013 and SEBI Research Analyst Regulations, 2014 — anyone giving specific buy/sell recommendations or return/performance claims for a fee needs to be registered under one of these.

This matters here, specifically, because several Nexarch features sit right next to that line by design:
- **Investor Strategy Overview** copy ("Focuses on long-term compounders...") must stay descriptive of historical behavior, never framed as a recommendation to replicate it.
- **Portfolio Health** indicators must stay objective and observational — this is also why [product-requirements.md](./product-requirements.md) explicitly rejects a single "trust score," since a score is a much shorter step from "this is what the data shows" to "this is what you should do."
- **Discovery filters by strategy** ("Value Investors," "Momentum Traders") are fine as descriptive labels of what a portfolio already does; they become risky the moment UI copy implies "invest like this."
- **Phase 4 monetization** (creator subscriptions, "exclusive research," "subscription-based insights" per [product/monetization.md](./product/monetization.md)) is the highest-risk area of all — several real finfluencers have already had to become registered Research Analysts or Investment Advisers specifically to keep selling paid insights legally. Any Nexarch creator monetizing "research" likely needs the same registration, and Nexarch's own platform obligations around facilitating that should get dedicated legal review before Phase 4, not discovered afterward.

None of this blocks Phase 1–3 work. It's a standing constraint on copy and feature design that should be checked at design time on every feature touching strategy/health/recommendations, and a hard legal-review gate specifically before Phase 4. Logged as a recurring item in [decisions.md](./decisions.md) rather than a one-time note, since it needs to be re-checked as features get added, not signed off once.

## Incident Response Basics

- All broker connection events (connect, disconnect, sync, error, token refresh) logged to `audit_logs` (see [database.md](./database.md)).
- Structured application logging with alerting on anomalies (spike in failed syncs, spike in auth failures).
- A documented incident-response runbook (who's on call, how a broker-token leak would be contained and disclosed) should exist before real user broker tokens are stored in production — this is a pre-launch checklist item, not a someday item.
- Independent security review / basic penetration test recommended before public launch, given the sensitivity of what's being stored.
