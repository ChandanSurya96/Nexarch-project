"""Canonical strategy-category taxonomy — the fixed filter list from
docs/product-requirements.md "Feature: Investor Discovery Feed".

Single source of truth for the 8 categories, shared by scripts/seed_public_investors.py
(manual curation for Public Investor Library entries) and
app/services/strategy_categorization_service.py (rules-based auto-tagging
for verified portfolios, Milestone 7, ADR-028) — the same slugs, name, and
description text either path uses.
"""

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
