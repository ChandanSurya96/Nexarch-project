# User Feedback

**Purpose:** How feedback gets collected, categorized, and turned into backlog items — and the running log itself, once there's feedback to log. As of this writing (Phase 0, pre-launch), there are no real users yet, so this document is a process definition and an empty template, not a populated log. Update the log below as real feedback arrives; don't leave this file looking "finished" once it's actually in use.

---

## Collection Channels (Phase 1)

Given chat, notifications, and community features are explicitly out of MVP scope (see [roadmap.md](../roadmap.md)), feedback intake for Phase 1 should stay similarly lightweight:
- A simple in-app feedback link (mailto or a lightweight form) rather than a full support/ticketing system
- Direct outreach to the earliest recruited verified profiles (see [go-to-market.md](./go-to-market.md)) — for a cold-start product, these early users are worth talking to directly rather than only relying on passive feedback forms
- Manual monitoring of any public mentions (social media, forums) during early launch, given the target communities named in go-to-market are exactly the kind of place early reactions will surface unprompted

## Categorization

When logging feedback, tag it against one of:
- **Bug** — something broken relative to [product-requirements.md](../product-requirements.md) acceptance criteria
- **Friction** — works as designed but is harder/more confusing than it should be
- **Feature request** — a new capability, to be evaluated against [roadmap.md](../roadmap.md) phasing before being added to [feature-backlog.md](./feature-backlog.md)
- **Trust/compliance concern** — anything suggesting a user perceived a feature as advice, or misunderstood what verification means — this category should route directly to a [security.md](../security.md) review, not just general product triage, given how central that distinction is to the whole product

## Log Template

| Date | Source | Feedback (paraphrased) | Category | Status | Linked Backlog Item |
|---|---|---|---|---|---|
| _e.g., 2026-08-15_ | _e.g., early verified user, direct outreach_ | _e.g., "Wasn't sure if disconnecting my broker deletes my old holdings or just stops updating them"_ | Friction | Open | _link once triaged_ |

*(Log starts empty — this row is a formatting example, not a real entry. Delete it once the first real feedback is logged.)*

## Review Cadence

Recommend a lightweight weekly pass through open feedback during Phase 1 (low volume, easy to review by hand), moving to a more structured triage process once volume justifies it — not before, since process overhead ahead of actual volume tends to just slow things down without benefit.
