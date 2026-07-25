"""Shared broker adapter interface.

Every broker/AA adapter implements this so the sync worker never needs to
know broker-specific details (see docs/architecture.md "Backend Structure").
Only Upstox is implemented in this milestone (ADR-012 — pilot broker); this
module is what makes adding Dhan/Angel One/etc. later additive rather than a
rewrite (per docs/roadmap.md Phase 1 scope).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, datetime


@dataclass(frozen=True)
class TokenPair:
    """Result of a successful auth-code exchange or token refresh."""

    access_token: str
    refresh_token: str | None
    expires_at: datetime | None


@dataclass(frozen=True)
class RawHolding:
    """A single holding exactly as a broker's API returns it, pre-normalization."""

    symbol: str
    isin: str | None
    exchange: str | None
    quantity: float
    avg_cost_price: float | None


@dataclass(frozen=True)
class PricePoint:
    """One day's closing price — the input to volatility calculations
    (see app/services/analytics_service.py, ADR-024)."""

    trade_date: date
    close: float


class BrokerAuthError(Exception):
    """Auth code exchange or token refresh failed (bad code, revoked, etc.)."""


class BrokerTokenExpiredError(Exception):
    """The stored access token has expired and needs a fresh connect/reconnect.

    Raised distinctly from BrokerAPIError so the sync worker can set
    broker_connections.status = 'expired' rather than 'error' (see
    docs/broker-integrations.md "Refresh Strategy").
    """


class BrokerRateLimitError(Exception):
    """The broker's API rate limit was hit; the sync worker should back off
    rather than retry immediately (see docs/broker-integrations.md "Security").
    """


class BrokerAPIError(Exception):
    """Any other broker API failure (network error, 5xx, unexpected shape)."""


class BrokerAdapter(ABC):
    """Interface every broker adapter implements."""

    broker_name: str

    @abstractmethod
    def get_login_url(self, redirect_uri: str, state: str) -> str:
        """Build the URL the frontend redirects the user to for broker login.

        `state` is an opaque, single-use, server-generated CSRF token (see
        broker_connection_service.init_connection/handle_callback) — the
        broker is expected to echo it back unchanged on redirect, per the
        OAuth2 `state` parameter convention.
        """

    @abstractmethod
    def exchange_code(self, auth_code: str, redirect_uri: str) -> TokenPair:
        """Exchange an OAuth auth code for an access (+ refresh) token.

        Raises:
            BrokerAuthError: if the code is invalid or the exchange fails.
        """

    @abstractmethod
    def fetch_holdings(self, access_token: str) -> list[RawHolding]:
        """Fetch the user's current holdings.

        Raises:
            BrokerTokenExpiredError: if the access token has expired.
            BrokerRateLimitError: if the broker's rate limit was hit.
            BrokerAPIError: for any other failure.
        """

    @abstractmethod
    def fetch_historical_prices(
        self, access_token: str, isin: str, exchange: str, from_date: date, to_date: date
    ) -> list[PricePoint]:
        """Daily closing prices for one instrument over [from_date, to_date] —
        the basis for the volatility calculation in analytics_service.py
        (ADR-024). Reuses the same broker access token as fetch_holdings;
        no separate market-data credential.

        Raises the same errors as fetch_holdings for the same reasons. An
        empty list (rather than an error) is an acceptable response for an
        instrument with no historical data available — the caller treats
        that as "not enough data for this holding," not a hard failure.
        """

    def refresh_token(self, refresh_token: str) -> TokenPair:
        """Exchange a refresh token for a new access token.

        Default: not supported. Upstox's analytics token (preferred — see
        docs/broker-integrations.md) doesn't need daily re-auth, so this is
        only overridden by adapters/paths that require it.
        """
        raise NotImplementedError(f"{self.broker_name} does not support token refresh.")
