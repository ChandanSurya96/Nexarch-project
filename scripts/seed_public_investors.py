"""Seed the Public Investor Library — 5 profiles, per docs/roadmap.md Phase 1.

Run from the project root, with the apps/api venv active and Postgres reachable:
    apps/api/venv/Scripts/python.exe scripts/seed_public_investors.py   (Windows)
    apps/api/venv/bin/python scripts/seed_public_investors.py            (macOS/Linux)

Idempotent: re-running updates bios/holdings in place rather than duplicating
(matched on PublicInvestor.slug).

DATA INTEGRITY — READ BEFORE EDITING THIS FILE:
docs/database.md is explicit that every Public Investor Library holding
"must be populated only from actual, dated, cited public shareholding
disclosures — never estimated or inferred." Every holding below was pulled
from a live, structured, dated source (Tickertape's per-investor shareholding
tables, which are themselves built from NSE/BSE shareholding-pattern
disclosures) on 2026-07-25 — see each investor's SOURCE_URL and AS_OF_DATE.
Only a handful of each investor's largest holdings are included, not their
full disclosed portfolio (some hold 40-70+ stocks) — a smaller, verified set
beats a complete but padded one. `isin` and `avg_cost_price` are left blank
throughout: ISINs weren't independently verified per holding, and acquisition
cost isn't public information for a third party's disclosed shareholding
(only the investor/broker would know it) — leaving both blank is honest,
not an oversight. market_cap_category uses the market-cap figure shown
alongside each holding on its source page, bucketed at the conventional
Indian large/mid/small-cap thresholds (~₹70,000cr / ~₹20,000cr).

If you add or update an investor here, keep this same discipline: a real
source_disclosure_url and a real as_of date, or don't add the row.
"""

from __future__ import annotations

import os
import sys
from datetime import date, datetime, timezone

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_API_DIR = os.path.join(_PROJECT_ROOT, "apps", "api")
sys.path.insert(0, _API_DIR)
# create_app()'s load_dotenv() searches upward from the current working
# directory, not from this file's location — chdir so it finds apps/api/.env
# regardless of where this script was invoked from.
os.chdir(_API_DIR)

from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402
from app.models.holding import Holding  # noqa: E402
from app.models.portfolio import Portfolio  # noqa: E402
from app.models.public_investor import PublicInvestor  # noqa: E402
from app.models.strategy_category import PortfolioStrategyTag, StrategyCategory  # noqa: E402

# NOT computing a PortfolioSnapshot here, deliberately: analytics_service's
# value math is quantity * avg_cost_price, and avg_cost_price is left blank
# below (see the module docstring). A first attempt at back-deriving a
# per-share price from each holding's disclosed crore-value produced a wildly
# wrong number for at least one holding on a sanity check against its real
# share price — exactly the kind of silently-wrong precision the product's
# own principles (ADR-008) warn against. Better for Public Investor Library
# analytics to be honestly absent (GET .../analytics already returns null
# health when there's no snapshot) than quietly incorrect. Revisit once
# there's a verified value source for these disclosures, not before.

# ── Strategy categories — the filter list from docs/product-requirements.md ──
STRATEGY_CATEGORIES = [
    {"name": "Long-term", "slug": "long-term", "description": "Holds positions for years, not quarters."},
    {"name": "Growth", "slug": "growth", "description": "Favors companies expanding revenue/earnings quickly."},
    {"name": "Value", "slug": "value", "description": "Favors companies priced below intrinsic worth."},
    {"name": "Dividend", "slug": "dividend", "description": "Favors steady dividend-paying businesses."},
    {"name": "Momentum", "slug": "momentum", "description": "Favors stocks with strong recent price trends."},
    {"name": "ETF", "slug": "etf", "description": "Primarily invests via exchange-traded funds."},
    {
        "name": "Small-cap Specialist",
        "slug": "small-cap-specialist",
        "description": "Concentrates on small-cap companies.",
    },
    {"name": "Low-risk", "slug": "low-risk", "description": "Favors capital preservation over upside."},
]

# ── Public Investor Library seed data ────────────────────────────────────────
# Every source_disclosure_url below was visited and read on 2026-07-25.
INVESTORS = [
    {
        "name": "Radhakishan Damani",
        "slug": "radhakishan-damani",
        "bio": (
            "Founder of Avenue Supermarts (D-Mart) and a long-time value investor "
            "known for a low-churn, cash-flow-focused approach to public markets."
        ),
        "source_disclosure_url": "https://www.tickertape.in/stocks/collections/radhakishan-damani-portfolio",
        "as_of_date": date(2026, 1, 30),
        "strategy_tags": ["long-term", "value"],
        "holdings": [
            {
                "symbol": "DMART",
                "quantity": 437_444_720,
                "sector": "Consumer",
                "market_cap_category": "large",
            },
            {
                "symbol": "VSTIND",
                "quantity": 49_430_148,
                "sector": "Consumer",
                "market_cap_category": "small",
            },
            {
                "symbol": "UBL",
                "quantity": 3_249_312,
                "sector": "Consumer",
                "market_cap_category": "mid",
            },
            {
                "symbol": "BFUTILITIE",
                "quantity": 381_000,
                "sector": "Industrials",
                "market_cap_category": "small",
            },
        ],
    },
    {
        "name": "Ashish Kacholia",
        "slug": "ashish-kacholia",
        "bio": (
            "A Mumbai-based investor and former head of research at Edelweiss Capital, "
            "known for identifying small- and mid-cap companies early in their growth cycle."
        ),
        "source_disclosure_url": "https://www.tickertape.in/stocks/collections/ashish-kacholia-portfolio",
        "as_of_date": date(2026, 1, 30),
        "strategy_tags": ["small-cap-specialist", "growth"],
        "holdings": [
            {
                "symbol": "BETA",
                "quantity": 1_263_826,
                "sector": "Pharma",
                "market_cap_category": "small",
            },
            {
                "symbol": "SHAILY",
                "quantity": 2_393_680,
                "sector": "Industrials",
                "market_cap_category": "small",
            },
            {
                "symbol": "XPROINDIA",
                "quantity": 918_550,
                "sector": "Industrials",
                "market_cap_category": "small",
            },
            {
                "symbol": "MANINDS",
                "quantity": 2_277_029,
                "sector": "Industrials",
                "market_cap_category": "small",
            },
        ],
    },
    {
        "name": "Vijay Kedia",
        "slug": "vijay-kedia",
        "bio": (
            "Founder of Kedia Securities, known for the 'SMILE' framework — small "
            "companies with medium experience, large ambition, and extra-large market potential."
        ),
        "source_disclosure_url": "https://www.tickertape.in/stocks/collections/vijay-kedia-portfolio",
        "as_of_date": date(2026, 1, 30),
        "strategy_tags": ["small-cap-specialist", "long-term"],
        "holdings": [
            {
                "symbol": "NEULANDLAB",
                "quantity": 2_025_000,
                "sector": "Pharma",
                "market_cap_category": "mid",
            },
            {
                "symbol": "ELECON",
                "quantity": 2_010_632,
                "sector": "Industrials",
                "market_cap_category": "small",
            },
            {
                "symbol": "ATULAUTO",
                "quantity": 2_250_000,
                "sector": "Auto",
                "market_cap_category": "small",
            },
            {
                "symbol": "VAIBHAVGBL",
                "quantity": 1_000_000,
                "sector": "Consumer",
                "market_cap_category": "small",
            },
        ],
    },
    {
        "name": "Dolly Khanna",
        "slug": "dolly-khanna",
        "bio": (
            "A Chennai-based investor whose portfolio, managed with her husband Rajiv "
            "Khanna, focuses on under-researched small- and mid-cap companies across "
            "manufacturing, chemicals, and consumer sectors."
        ),
        "source_disclosure_url": "https://www.tickertape.in/stocks/collections/dolly-khanna-portfolio",
        "as_of_date": date(2026, 2, 4),
        "strategy_tags": ["small-cap-specialist", "value"],
        "holdings": [
            {
                "symbol": "GHCL",
                "quantity": 987_735,
                "sector": "Materials",
                "market_cap_category": "small",
            },
            {
                "symbol": "SPIC",
                "quantity": 4_863_915,
                "sector": "Materials",
                "market_cap_category": "small",
            },
            {
                "symbol": "SDBL",
                "quantity": 4_293_853,
                "sector": "Consumer",
                "market_cap_category": "small",
            },
            {
                "symbol": "COFFEEDAY",
                "quantity": 3_632_065,
                "sector": "Consumer",
                "market_cap_category": "small",
            },
        ],
    },
    {
        "name": "Mukul Agrawal",
        "slug": "mukul-agrawal",
        "bio": (
            "Founder and chairman of Param Capital Group, known for a research-led "
            "approach to small- and mid-cap investing since the early 1990s."
        ),
        "source_disclosure_url": "https://www.tickertape.in/stocks/collections/mukul-agrawal-portfolio",
        "as_of_date": date(2026, 2, 4),
        "strategy_tags": ["small-cap-specialist", "growth"],
        "holdings": [
            {
                "symbol": "NEULANDLAB",
                "quantity": 400_000,
                "sector": "Pharma",
                "market_cap_category": "mid",
            },
            {
                "symbol": "RADICO",
                "quantity": 1_400_083,
                "sector": "Consumer",
                "market_cap_category": "mid",
            },
            {
                "symbol": "NUVAMA",
                "quantity": 2_500_000,
                "sector": "Financials",
                "market_cap_category": "mid",
            },
            {
                "symbol": "PTCIL",
                "quantity": 160_000,
                "sector": "Materials",
                "market_cap_category": "mid",
            },
        ],
    },
]


def seed_strategy_categories() -> dict[str, StrategyCategory]:
    by_slug: dict[str, StrategyCategory] = {}
    for entry in STRATEGY_CATEGORIES:
        category = StrategyCategory.query.filter_by(slug=entry["slug"]).first()
        if category is None:
            category = StrategyCategory(**entry)
            db.session.add(category)
            db.session.flush()
        else:
            category.description = entry["description"]
        by_slug[entry["slug"]] = category
    db.session.commit()
    return by_slug


def seed_investors(categories_by_slug: dict[str, StrategyCategory]) -> None:
    for entry in INVESTORS:
        investor = PublicInvestor.query.filter_by(slug=entry["slug"]).first()
        if investor is None:
            investor = PublicInvestor(name=entry["name"], slug=entry["slug"])
            db.session.add(investor)
            db.session.flush()

        investor.bio = entry["bio"]
        investor.source_disclosure_url = entry["source_disclosure_url"]
        investor.last_disclosure_update = datetime.combine(
            entry["as_of_date"], datetime.min.time(), tzinfo=timezone.utc
        )

        portfolio = Portfolio.query.filter_by(public_investor_id=investor.id).first()
        if portfolio is None:
            portfolio = Portfolio(
                public_investor_id=investor.id,
                portfolio_type="public",
                is_public=True,
            )
            db.session.add(portfolio)
            db.session.flush()

        # Re-seeding replaces holdings/tags rather than duplicating them.
        Holding.query.filter_by(portfolio_id=portfolio.id).delete()
        for holding in entry["holdings"]:
            db.session.add(
                Holding(
                    portfolio_id=portfolio.id,
                    symbol=holding["symbol"],
                    isin=None,
                    exchange="NSE",
                    quantity=holding["quantity"],
                    avg_cost_price=None,
                    sector=holding["sector"],
                    market_cap_category=holding["market_cap_category"],
                    as_of_date=entry["as_of_date"],
                )
            )

        PortfolioStrategyTag.query.filter_by(portfolio_id=portfolio.id).delete()
        for slug in entry["strategy_tags"]:
            db.session.add(
                PortfolioStrategyTag(
                    portfolio_id=portfolio.id, strategy_category_id=categories_by_slug[slug].id
                )
            )

        db.session.commit()
        print(f"  seeded: {entry['name']} ({len(entry['holdings'])} holdings)")


if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        print("Seeding strategy categories...")
        categories = seed_strategy_categories()
        print(f"  {len(categories)} categories ready")

        print("Seeding Public Investor Library...")
        seed_investors(categories)
        print("Done.")
