"""Investor Strategy Overview — rules-based, descriptive-only summary copy.

See docs/product-requirements.md "Feature: Investor Strategy Overview":
copy must describe observed historical composition, never a recommendation
("you should hold these sectors") or a promise ("this strategy delivers
strong returns"). This is the single feature most likely to be read as
advice if the copy isn't deliberately descriptive (docs/security.md) — every
template below is worded as an observation about currently synced holdings,
never an instruction or a projection.

Phase 1 is templated off sector concentration + market-cap mix (no
"turnover" — Nexarch has no transaction-level data, only point-in-time
holdings, per docs/database.md). Phase 3's AI-generated version must inherit
this same constraint, not a looser one.
"""

from __future__ import annotations

from app.models.holding import Holding
from app.services.analytics_service import compute_market_cap_allocation

_MARKET_CAP_LABELS = {"large": "large-cap", "mid": "mid-cap", "small": "small-cap"}

# HHI bands — see compute_hhi in analytics_service.py for the underlying math.
_HIGH_CONCENTRATION_HHI = 0.5
_MODERATE_CONCENTRATION_HHI = 0.25


def _market_cap_phrase(holdings: list[Holding]) -> str:
    allocation = compute_market_cap_allocation(holdings)
    if not allocation:
        return ""
    dominant_category, weight = max(allocation.items(), key=lambda kv: kv[1])
    if weight <= 0.5:
        # <= not <: an exact 50/50 split has no dominant category either —
        # "predominantly" would misdescribe a tie as a majority.
        return ""
    label = _MARKET_CAP_LABELS.get(dominant_category, dominant_category)
    return f", predominantly in {label} holdings"


def generate_overview(
    sector_allocation: dict[str, float], hhi: float, holdings: list[Holding]
) -> str | None:
    """Returns a one-sentence, descriptive-only overview, or None if there's
    not yet enough synced data to say anything (honest absence, not a
    fabricated-sounding default — see ADR-008's same reasoning)."""
    if not sector_allocation:
        return None

    dominant_sector, dominant_weight = max(sector_allocation.items(), key=lambda kv: kv[1])
    market_cap_phrase = _market_cap_phrase(holdings)

    if hhi >= _HIGH_CONCENTRATION_HHI:
        return (
            f"Currently concentrated in {dominant_sector}, which makes up the majority of "
            f"synced holdings{market_cap_phrase}."
        )
    if hhi > _MODERATE_CONCENTRATION_HHI:
        # Strictly greater than: an exactly-even split across 4 sectors (HHI
        # == 0.25) reads as diversified, not "weighted toward" one of them.
        return (
            f"Currently weighted toward {dominant_sector} ({round(dominant_weight * 100)}% of "
            f"synced holdings), with exposure spread across other sectors as well"
            f"{market_cap_phrase}."
        )

    other_sectors = [s for s in sector_allocation if s != dominant_sector]
    top_others = sorted(other_sectors, key=lambda s: sector_allocation[s], reverse=True)[:2]
    sector_list = ", ".join([dominant_sector, *top_others])
    return f"Currently diversified across sectors including {sector_list}{market_cap_phrase}."
