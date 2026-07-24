# Competitor Analysis

**Purpose:** Who else solves pieces of the problem Nexarch is going after, what they do well, and where the actual gap is. Checked against current sources in July 2026 rather than assumed — competitor feature sets and positioning change fast enough that this should be re-verified periodically, not treated as permanent. See [vision.md](../vision.md) for how Nexarch is positioned relative to these categories, and [market-research.md](./market-research.md) for the broader context.

---

## The Core Finding

There is no direct India competitor doing what Nexarch does: **public, verified investor discovery as the primary product**, rather than a secondary feature bolted onto trading or personal tracking. The closest conceptual analog is a US app, not an Indian one — and it goes further into copy-trading than Nexarch's MVP intends to (see Dub, below). That gap is either a real opportunity or a real reason nobody's built it yet (regulatory friction, thin willingness-to-pay, unclear moat) — worth treating as an open question to validate, not a foregone conclusion in Nexarch's favor.

## By Category

### Brokers / Trading Platforms — Zerodha, Groww, Upstox, Angel One
**What they do well:** execution, low costs, huge user bases (India crossed roughly 21.6 crore total demat accounts by December 2025, split across CDSL's much larger retail account base and NSDL's much larger asset-under-custody share). Several now expose developer APIs Nexarch itself may integrate against (see [broker-integrations.md](../broker-integrations.md)).
**Gap Nexarch addresses:** none of these are built around public discovery of *other* investors' portfolios — their entire product surface is a private, single-user dashboard plus execution tools.

### Research Platforms — Screener.in, Trendlyne
**What they do well:** company-level fundamental analysis, and in Trendlyne's case, some public-investor / bulk-deal tracking features.
**Gap Nexarch addresses:** these are stock-first, not investor-first — the unit of analysis is a company, not a person's overall portfolio and behavior over time.

### Personal Portfolio Trackers — INDmoney, MProfit, Tickertape, Sharesight
**What they do well:** exactly the "consolidate my own holdings across brokers" problem — INDmoney aggregates across brokers/asset classes for free with automatic XIRR and tax-report generation; MProfit is the CA-favored choice for multi-asset (including PMS/AIF) household tracking; Tickertape (from the smallcase team) connects directly to Zerodha/Angel One/Upstox and layers in a fundamentals screener; Sharesight is the global freemium option with strong dividend-tracking, capped at 10 free holdings.
**Gap Nexarch addresses:** every one of these is fundamentally a *private, single-user* tool. None of them are built for *public* profiles, discovery, or following other people's verified portfolios — the entire "investor identity" and "discovery feed" layer that's the actual core of Nexarch's product simply doesn't exist in this category.

### Thematic / Model-Portfolio Investing — smallcase
**What they do well:** curated, theme-based model portfolios that can be invested into directly through a partner broker.
**Gap Nexarch addresses:** smallcase portfolios are curated products, not individual people's real, evolving personal portfolios — it's a different unit entirely (a packaged product vs. a personal track record).

### Social / Copy-Trading — Dub (United States)
**What they do:** the closest conceptual sibling to Nexarch's discovery premise — "discover real investors, follow their strategies" — but Dub goes a full step further into **automatic capital-moving copy-trading**: tapping "Copy" mirrors that investor's real trades into your own brokerage account, executed through Dub's own SEC-registered broker-dealer and investment-adviser affiliates, with SIPC insurance on the brokerage side. It also tracks disclosed trades of U.S. politicians and public filings, and has layered in a subscription tier (roughly $9.99/mo or $89.99/yr) plus an asset-based management fee (0–2.5%/yr) on "Premium Creator" portfolios.
**Why this matters for Nexarch, not as a template but as a warning label:** Dub's model only works legally because it operates *inside* a full US broker-dealer/RIA regulatory wrapper. Building toward that model in India without the equivalent SEBI registrations (stockbroker, portfolio manager, or investment adviser depending on the exact mechanics) would be a serious compliance gap, not a growth feature — which is exactly why [roadmap.md](../roadmap.md) treats even *optional* execution as a Phase 5, separately-lawyered undertaking rather than a natural Phase 2 extension of "following." Nexarch's MVP explicitly stops at "follow, no capital moves" — see the Following acceptance criteria in [product-requirements.md](../product-requirements.md).

## Positioning Table (updated from the founding concept note)

| Platform | Primary Focus | Public investor discovery? | Moves real money? |
|---|---|---|---|
| Zerodha / Groww / Upstox | Trading & investing | No | Yes (execution) |
| Trendlyne | Research & some public-investor data | Partial | No |
| Screener.in | Fundamental analysis | No | No |
| Smallcase | Thematic model portfolios | No | Yes (via broker) |
| INDmoney / MProfit / Tickertape / Sharesight | Personal portfolio tracking | No | No |
| Dub (US) | Social copy-trading | Yes | Yes (via SEC-regulated wrapper) |
| **Nexarch** | **Portfolio identity, verification & discovery** | **Yes** | **No (by design, through Phase 4)** |

## What to Watch

- Whether Trendlyne or Tickertape (both of which already touch adjacent pieces — bulk-deal tracking and broker connectivity respectively) extend further into public investor-discovery territory before Nexarch ships.
- Whether any Indian platform attempts a Dub-style copy-trading model under a proper SEBI-regulated wrapper — that would be the first genuinely direct competitor, and worth tracking specifically because it would validate the demand thesis even while raising the competitive bar.
