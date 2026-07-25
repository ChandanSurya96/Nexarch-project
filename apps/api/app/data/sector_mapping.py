"""Static ISIN → (sector, market_cap_category) enrichment reference (ADR-013).

Brokers don't reliably return sector or market-cap category in holdings
responses (see docs/broker-integrations.md), and no market-data vendor is
selected yet (ADR-008 defers that decision to Phase 2). This is a small,
manually-curated seed covering commonly-held large-cap NSE names, in the same
spirit as the Public Investor Library's manual curation.

IMPORTANT: entries below were compiled from general knowledge, not fetched
from an authoritative source at write time. Verify against NSE/BSE's official
ISIN master data before depending on this for anything beyond local
development/testing — this is exactly the kind of "looks precise but isn't
verified" gap the product's own principles (ADR-008) warn against presenting
as fact. Extend this dict as real pilot users' holdings surface unmapped
ISINs; an unmapped ISIN should get `sector=None`/`market_cap_category=None`,
never a guess (see normalization_service.py).

Keyed by ISIN (the most reliable cross-source join key per
docs/broker-integrations.md, since trading symbols can differ between NSE and
BSE listings of the same security).
"""

SECTOR_MAPPING: dict[str, dict[str, str]] = {
    "INE002A01018": {"sector": "Energy", "market_cap_category": "large"},  # Reliance Industries
    "INE467B01029": {"sector": "IT", "market_cap_category": "large"},  # Tata Consultancy Services
    "INE040A01034": {"sector": "Financials", "market_cap_category": "large"},  # HDFC Bank
    "INE009A01021": {"sector": "IT", "market_cap_category": "large"},  # Infosys
    "INE090A01021": {"sector": "Financials", "market_cap_category": "large"},  # ICICI Bank
    "INE030A01027": {"sector": "Consumer", "market_cap_category": "large"},  # Hindustan Unilever
    "INE154A01025": {"sector": "Consumer", "market_cap_category": "large"},  # ITC
    "INE062A01020": {"sector": "Financials", "market_cap_category": "large"},  # State Bank of India
    "INE397D01024": {"sector": "Telecom", "market_cap_category": "large"},  # Bharti Airtel
    "INE237A01028": {"sector": "Financials", "market_cap_category": "large"},  # Kotak Mahindra Bank
    "INE018A01030": {"sector": "Industrials", "market_cap_category": "large"},  # Larsen & Toubro
    "INE296A01024": {"sector": "Financials", "market_cap_category": "large"},  # Bajaj Finance
    "INE021A01026": {"sector": "Consumer", "market_cap_category": "large"},  # Asian Paints
    "INE585B01010": {"sector": "Auto", "market_cap_category": "large"},  # Maruti Suzuki
    "INE860A01027": {"sector": "IT", "market_cap_category": "large"},  # HCL Technologies
    "INE238A01034": {"sector": "Financials", "market_cap_category": "large"},  # Axis Bank
    "INE044A01036": {"sector": "Pharma", "market_cap_category": "large"},  # Sun Pharmaceutical
    "INE280A01028": {"sector": "Consumer", "market_cap_category": "large"},  # Titan Company
    "INE075A01022": {"sector": "IT", "market_cap_category": "large"},  # Wipro
    "INE155A01022": {"sector": "Auto", "market_cap_category": "large"},  # Tata Motors
    "INE101A01026": {"sector": "Auto", "market_cap_category": "large"},  # Mahindra & Mahindra
    "INE481G01011": {"sector": "Materials", "market_cap_category": "large"},  # UltraTech Cement
    "INE733E01010": {"sector": "Utilities", "market_cap_category": "large"},  # NTPC
    "INE019A01038": {"sector": "Materials", "market_cap_category": "large"},  # JSW Steel
    "INE081A01012": {"sector": "Materials", "market_cap_category": "large"},  # Tata Steel
    "INE522F01014": {"sector": "Energy", "market_cap_category": "large"},  # Coal India
    "INE213A01029": {"sector": "Energy", "market_cap_category": "large"},  # ONGC
}


def enrich(isin: str | None) -> dict[str, str | None]:
    """Look up sector/market_cap_category for an ISIN.

    Returns {"sector": None, "market_cap_category": None} for an unmapped or
    missing ISIN — never a guessed value (see module docstring).
    """
    if not isin:
        return {"sector": None, "market_cap_category": None}
    return SECTOR_MAPPING.get(isin, {"sector": None, "market_cap_category": None})
