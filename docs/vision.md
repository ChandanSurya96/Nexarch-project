# Vision

**Purpose:** This document explains *why* Nexarch exists, what it believes, and what it deliberately refuses to become. Every product and engineering decision should be traceable back to something on this page. See also [roadmap.md](./roadmap.md) for how this becomes a plan, and [product-requirements.md](./product-requirements.md) for how it becomes features.

---

## The Problem

India added roughly 21.6 crore demat accounts by the end of 2025, and retail participation keeps climbing — but the information layer around that growth hasn't kept pace. Most new investors get their market education from YouTube, Instagram, Telegram groups, and X, where opinions circulate freely and accountability doesn't. Screenshots can be cropped. Losing trades quietly disappear. There's no cost to being confidently wrong.

Existing platforms don't fill this gap because they aren't built to:
- **Brokers** (Zerodha, Groww, Upstox...) focus on execution — buying and selling — not on who you should trust.
- **Research platforms** (Screener.in, Trendlyne) focus on company fundamentals, not investor track records.
- **Portfolio trackers** (INDmoney, MProfit, Tickertape) focus on *your own* consolidated view across brokers, not on discovering and evaluating *other* investors.

Nobody owns the question retail investors actually ask themselves before following someone's lead: *"Can I trust this person's investing ability?"*

## Core Philosophy

> **"Show your portfolio, not your opinions."**

Trust should be a function of transparency, not charisma. Instead of asking users to take an influencer's word for it, Nexarch shows the portfolio itself — holdings, allocation, consistency over time — and lets the person judge for themselves. Verification here means one specific, narrow thing: *this data came directly from an authenticated brokerage account and wasn't typed in by hand.* It is not a claim about skill, and it is never a promise of returns.

This distinction matters enough that it's worth stating twice, in plain language, because it's the thing most likely to get eroded under product-growth pressure later: **Nexarch shows what a portfolio *is*, never what someone *should do*.** The moment a feature crosses from "here's what this portfolio holds" to "here's what you should buy," it has left transparency and entered advice — a different product, with a different regulator. See [security.md](./security.md) for why this isn't just a philosophical line.

## Mission

To build an ecosystem where every investor can earn a reputation through transparent, verified portfolio sharing — helping retail investors make better-informed decisions without needing to trust a stranger's word for it.

## Long-Term Vision

To become India's default digital identity layer for investors:

| Platform | Identity Layer For |
|---|---|
| LinkedIn | Professional identity |
| GitHub | Developer identity |
| **Nexarch** | **Investor identity** |

A portfolio profile on Nexarch should eventually mean something the way a well-maintained GitHub profile does — a durable, checkable record, not a snapshot of a good month.

## Product Positioning

Nexarch sits in a gap between three categories that each solve an adjacent problem, without solving this one:

- **vs. Brokers/Trading Apps** — Nexarch is not a broker and never touches order execution in the MVP. It reads; it doesn't act.
- **vs. Research Platforms** — Nexarch is about *people and portfolios*, not company fundamentals.
- **vs. Portfolio Trackers** — Nexarch is a *public discovery network*, not a private dashboard. The unit of value is a shareable, comparable profile, not a personal net-worth view.

Full competitive detail lives in [product/competitor-analysis.md](./product/competitor-analysis.md).

## Core Principles

**What every feature should reinforce:**
- **Transparency** — real data over claims
- **Trust** — earned through consistency, not manufactured through a score
- **Simplicity** — one honest metric beats five vanity ones
- **Performance** — a slow product undermines a trust product
- **Professionalism** — this handles people's financial identity; it should feel like it

**What every feature should actively resist:**
- Fake social metrics (inflated follower counts, engagement bait)
- Clickbait ("This portfolio returned 400%!" without context)
- Clutter (a feature for every idea)
- Over-engineering (solving Phase 4 problems in Phase 1)

## Explicit Non-Goals (for now)

Stated once here so they don't quietly creep back in feature-by-feature:
- Nexarch does not execute trades in the MVP, and won't until Phase 5 — and even then, only "subject to regulatory compliance," which is doing real work in that sentence, not a formality.
- Nexarch does not assign a single subjective "trust score." See [product-requirements.md](./product-requirements.md) for why objective health indicators replace this.
- Nexarch does not give investment advice, and no feature should be worded in a way that reads as advice. This is not a legal disclaimer bolted on afterward — it has to be true of the actual UI copy. See [security.md](./security.md).

## Why This Matters Now

SEBI has spent 2024–2026 actively tightening the rules around unregistered "finfluencers" giving disguised investment advice, up to and including a ₹546 crore enforcement action in December 2025 against an academy found to be running advisory services under the label of "education." That's not a reason to avoid this space — if anything it's the strongest possible validation of the founding premise, that unaccountable opinion is a real problem worth solving. But it's also the clearest signal available that *how* Nexarch frames portfolio data matters as much as the data itself. See [security.md](./security.md) and [product/monetization.md](./product/monetization.md) for how this shapes specific product decisions.
