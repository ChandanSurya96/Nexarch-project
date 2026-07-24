# Monetization

**Purpose:** Detail behind the three-tier revenue model from the founding concept note (Free / Premium / Creator Economy), plus the regulatory considerations that should shape *how* each tier is built, not just *whether* it exists. See [roadmap.md](../roadmap.md) for phasing and [security.md](../security.md) for the underlying compliance reasoning this builds on.

---

## Free Tier (Phase 1+)

- Investor discovery and browsing
- Public profiles and Public Investor Library
- Basic portfolio analytics (allocation, sector split, HHI-based diversification/concentration — see [product-requirements.md](../product-requirements.md))

This tier isn't a loss-leader afterthought — it's the entire cold-start and trust-building mechanism. Monetizing too early or too aggressively against core discovery would undermine the "transparency over hype" positioning before it's established. No specific pricing changes proposed to this tier at this stage.

## Premium Tier (Phase 2+)

Illustrative feature set (pricing TBD — needs real willingness-to-pay validation, not a guess baked into this document):
- Advanced portfolio analytics (deeper historical trend views, comparisons)
- AI-generated portfolio explanations (Phase 3) — must inherit the same descriptive-only, non-advisory constraint as the free-tier version; charging for a feature doesn't loosen the compliance bar, if anything it tightens scrutiny of what's actually being sold
- Portfolio comparisons (side-by-side)
- Smart alerts (compatible with staying out of "Notifications" MVP scope, since this is a Phase 2+ feature, not Phase 1)
- Premium discovery filters

## Creator Economy (Phase 4) — Read This Section Before Building Anything Here

This is the highest-regulatory-risk part of the entire product, and it deserves more caution here than a standard "revenue stream" writeup would normally get.

**The mechanism as described in the founding concept note:** verified investors monetize through premium portfolio access, exclusive research, educational communities, and subscription-based insights, with Nexarch taking a platform commission.

**Why this needs a hard legal gate before it ships (see [feature-backlog.md](./feature-backlog.md) Phase 4):** "exclusive research" and "subscription-based insights" sold for a fee are close to a textbook description of activity regulated under the SEBI Research Analyst Regulations, 2014 and SEBI Investment Adviser Regulations, 2013. This isn't a hypothetical or overcautious reading — it's the exact fact pattern SEBI has been actively enforcing against in the finfluencer space since 2024, up to and including a December 2025 order impounding roughly ₹546 crore from an operator SEBI found to be running unregistered advisory services under an educational label. Several legitimate finance creators have already restructured specifically to obtain RA or IA registration in order to keep selling paid content legally.

**What this means concretely for Nexarch's design, not just its legal team:**
- Any creator monetizing "research" or "insights" through Nexarch likely needs their own SEBI RA or IA registration — Nexarch's onboarding for paid creators should check for and require this, not assume it's the creator's problem alone.
- Nexarch itself, as the platform facilitating that monetization and taking a commission, should get its own legal assessment of what obligations that facilitation role creates — this is a question for securities counsel, not something this document can resolve.
- Product copy for any paid tier needs the same descriptive-vs-advisory discipline as the free discovery feed (see [security.md](../security.md)) — a paywall doesn't change what the content legally is.

**Recommendation:** treat the legal review as a literal go/no-go gate on Phase 4, not a parallel workstream that can lag behind engineering. This is logged as a P0 hard-gate backlog item in [feature-backlog.md](./feature-backlog.md).

## What's Explicitly Not Being Proposed

- No brokerage/execution commission model until Phase 5 at the earliest, and only after Phase 5's own separate regulatory scoping (see [roadmap.md](../roadmap.md)).
- No advertising model has been discussed in the founding materials or proposed here — Nexarch's trust-first positioning would be directly undermined by anything that looks like paid placement in the discovery feed, and this document deliberately doesn't introduce that idea.

## Unit Economics — Open Question

No cost/revenue modeling has been done yet at this stage (Phase 0), because it depends on decisions not yet made: which broker integrations end up in the mix (Groww's ₹499/month *user*-side API fee, per [broker-integrations.md](../broker-integrations.md), is a real adoption-cost input if Groww support is prioritized), AA integration overhead (ADR-010), and eventual market-data vendor costs (ADR-008). Worth a real modeling pass once Phase 1 is far enough along to have actual sync-volume and infrastructure-cost data, rather than guessing now.
