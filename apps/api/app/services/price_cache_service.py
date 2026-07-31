"""Redis cache for broker historical price series (ADR-037).

Daily closing prices for a *past* date range are immutable — yesterday's
close does not change — which makes them an unusually safe thing to cache.
That matters here because the same instrument is fetched over and over:
`sync_service` fetches prices per holding, so every portfolio holding
RELIANCE triggers its own identical call, on every sync. Caching collapses
all of those onto one broker request per (instrument, window) per TTL.

Only market data is cached — never holdings, quantities, or anything
user-specific. The cache key contains an ISIN and a date range, nothing
tied to a user or portfolio, so two users holding the same stock share a
cache entry without either learning anything about the other.

Deliberately free of Flask globals (no current_app): these functions are
called from sync worker *threads*, which do not inherit an application
context, so anything touching current_app would raise there. TTL is passed
in by the caller, which resolves it from config on the main thread.

Fails open by design: any Redis error is swallowed and treated as a cache
miss. A cache outage should make sync slower, never make it fail — the
broker call remains the source of truth.
"""

from __future__ import annotations

import json
from datetime import date

from app.extensions import redis_client

_KEY_PREFIX = "prices:"
DEFAULT_TTL_SECONDS = 24 * 60 * 60


def _key(isin: str, exchange: str, from_date: date, to_date: date) -> str:
    return f"{_KEY_PREFIX}{isin}:{exchange}:{from_date.isoformat()}:{to_date.isoformat()}"


def get_closes(isin: str, exchange: str, from_date: date, to_date: date) -> list[float] | None:
    """Cached closing prices, or None on a miss."""
    try:
        raw = redis_client.get(_key(isin, exchange, from_date, to_date))
    except Exception:
        return None  # cache unreachable — behave as a miss
    if raw is None:
        return None
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        return None  # corrupt/legacy entry — treat as a miss, never fail the sync
    return parsed if isinstance(parsed, list) else None


def set_closes(
    isin: str,
    exchange: str,
    from_date: date,
    to_date: date,
    closes: list[float],
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
) -> None:
    """Cache a price series. Empty series are deliberately NOT cached.

    An empty response means "no historical data for this instrument" — which
    is a legitimate answer per the BrokerAdapter contract, but is also what a
    transient broker hiccup looks like. Caching it would suppress that
    holding's volatility for the whole TTL (a day) on the strength of one bad
    response, and the failure would be invisible. Not caching empties makes
    the miss self-healing on the next sync, at the cost of re-asking for
    genuinely dataless instruments — the cheaper mistake of the two.
    """
    if not closes:
        return
    try:
        redis_client.set(
            _key(isin, exchange, from_date, to_date), json.dumps(closes), ex=ttl_seconds
        )
    except Exception:
        # Never let a cache write failure break a sync that already succeeded.
        pass
