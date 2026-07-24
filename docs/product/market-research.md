# Market Research

**Purpose:** Market sizing and context for Nexarch, sourced rather than assumed. Figures below are current as of mid-2026 sources and should be re-checked periodically — this document has a shelf life, unlike most of the rest of this folder. See [competitor-analysis.md](./competitor-analysis.md) for who's already operating in this space, and [vision.md](../vision.md) for why the gap described here matters.

---

## Retail Investor Growth

India's total demat account base reached roughly **21.6 crore (216 million)** by December 2025. The two depositories serve different segments of that base:

- **CDSL** carries the larger share of individual retail accounts — roughly 18.0 crore accounts as of end-March 2026, growing to about 18.4 crore by end-May 2026, after adding about 2.7 crore new accounts during FY26 alone.
- **NSDL** carries far fewer accounts (about 4.5 crore as of May 2026) but a much larger share of total assets in custody, reflecting its historically stronger institutional and high-net-worth base — NSDL's custody value has been reported north of ₹520 lakh crore versus roughly ₹77 lakh crore for CDSL.

**A useful nuance, not just a growth headline:** even with NSDL posting its strongest-ever annual account addition in FY26, fresh account openings *industry-wide* actually declined by roughly 22% during the same year. Retail account growth in India is still substantial in absolute terms, but the post-pandemic hyper-growth phase (monthly additions running at 3+ million at the 2021–2024 peak) appears to be normalizing rather than continuing to accelerate. This matters for go-to-market planning (see [go-to-market.md](./go-to-market.md)): the addressable pool of *new* investors is growing more slowly than the pool of *existing* investors who might still be a fit for Nexarch's "prove your track record" premise.

## The Finfluencer Ecosystem — Growth and Regulatory Response

The retail-investing boom fueled a parallel boom in financial "creator" content across YouTube, Instagram, Telegram, and X — the exact ecosystem [vision.md](../vision.md) frames as the problem Nexarch responds to. That ecosystem is now under active, escalating SEBI enforcement:

- **2024:** SEBI began barring regulated entities (brokers, mutual funds, etc.) from associating with unregistered finfluencers who give securities advice or make performance claims.
- **January 2025:** a circular restricted finfluencers to using stock price data at least three months old in "educational" content, specifically to prevent real-time trading tips disguised as education.
- **December 2025:** SEBI's largest enforcement action to date against a finfluencer — an order impounding roughly ₹546 crore from an academy found to be running unregistered investment-advisory and research services under the label of education, including live buy/sell calls during trading sessions.
- **May 2026:** a new circular mandates that SEBI-registered entities and individuals display their registration name and number directly within their social media content, not just in a bio.

**Why this is relevant market context, not just a compliance footnote:** several prominent Indian finance creators have already restructured their businesses around formal SEBI registration (Research Analyst or Investment Adviser licenses) specifically to keep monetizing legally — evidence that the market is actively sorting itself into "registered, accountable" and "unregistered, now-restricted" categories. That sorting is happening independent of Nexarch, and it validates the underlying premise (verifiable accountability has real value) more than it validates any specific Nexarch feature. See [monetization.md](./monetization.md) for how this shapes Phase 4 planning specifically.

## Adjacent Infrastructure Worth Tracking

The RBI Account Aggregator framework's extension to securities data (NSDL and CDSL both live as Financial Information Providers as of 2026 — see [broker-integrations.md](../broker-integrations.md)) is itself a market signal: India's financial-data-sharing infrastructure is maturing toward exactly the kind of consented, standardized access Nexarch's core feature depends on. This is a tailwind for the entire category of "connect your accounts, get value" products, not specific to Nexarch, and worth watching for how quickly other players start building on it too.

## Open Research Questions

This document answers "how big and how fast is the underlying market," not "will people specifically want Nexarch" — that's a product-validation question, not a market-sizing one, and shouldn't be conflated with it. Worth a deliberate, small-scale validation pass (interviews with personas like the ones in [user-personas.md](./user-personas.md)) before Phase 1 investment scales up, rather than assuming market growth alone de-risks product-market fit.
