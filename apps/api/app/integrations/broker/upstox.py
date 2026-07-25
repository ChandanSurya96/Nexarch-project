"""Upstox adapter — Phase 1 pilot broker (ADR-012).

Implements BrokerAdapter against Upstox's v2 API (OAuth redirect + token
exchange, GET /v2/portfolio/long-term-holdings), per docs/broker-integrations.md.

Upstox is the pilot broker because holdings/portfolio access is free and it
supports a long-lived "extended" token that avoids the daily re-auth several
other brokers require (see docs/broker-integrations.md "Broker-by-Broker
Status").

VERIFY BEFORE PRODUCTION: Upstox's exact endpoint paths, request/response
field names, and token-lifetime behavior should be re-checked against Upstox's
current live API docs before this handles a real user connection — API
surfaces like this change over time, and docs/broker-integrations.md itself
flags this space as needing re-verification before any integration agreement.
All outbound HTTP is isolated in the two _http_* helpers below specifically so
this can be verified/adjusted without touching the rest of the adapter, and so
tests can mock it without live credentials.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta

import requests

from app.integrations.broker.base import (
    BrokerAdapter,
    BrokerAPIError,
    BrokerAuthError,
    BrokerRateLimitError,
    BrokerTokenExpiredError,
    RawHolding,
    TokenPair,
)

_LOGIN_URL = "https://api.upstox.com/v2/login/authorization/dialog"
_TOKEN_URL = "https://api.upstox.com/v2/login/authorization/token"
_HOLDINGS_URL = "https://api.upstox.com/v2/portfolio/long-term-holdings"

_REQUEST_TIMEOUT_SECONDS = 10


class UpstoxAdapter(BrokerAdapter):
    broker_name = "upstox"

    def __init__(self) -> None:
        self._api_key = os.environ.get("UPSTOX_API_KEY", "")
        self._api_secret = os.environ.get("UPSTOX_API_SECRET", "")

    def get_login_url(self, redirect_uri: str, state: str) -> str:
        return (
            f"{_LOGIN_URL}?response_type=code"
            f"&client_id={self._api_key}"
            f"&redirect_uri={redirect_uri}"
            f"&state={state}"
        )

    def exchange_code(self, auth_code: str, redirect_uri: str) -> TokenPair:
        resp = self._http_post_token(auth_code, redirect_uri)

        if resp.status_code != 200:
            raise BrokerAuthError(f"Upstox token exchange failed: {resp.status_code} {resp.text}")

        body = resp.json()
        access_token = body.get("access_token")
        if not access_token:
            raise BrokerAuthError("Upstox token exchange response missing access_token.")

        # Upstox access tokens expire daily at a fixed time (see
        # docs/broker-integrations.md "Refresh Strategy"); model this as
        # "expires at end of day" absent a more precise value from the response.
        expires_at = datetime.now(UTC) + timedelta(days=1)
        return TokenPair(
            access_token=access_token,
            refresh_token=body.get("extended_token"),
            expires_at=expires_at,
        )

    def fetch_holdings(self, access_token: str) -> list[RawHolding]:
        resp = self._http_get_holdings(access_token)

        if resp.status_code == 401:
            raise BrokerTokenExpiredError("Upstox access token has expired.")
        if resp.status_code == 429:
            raise BrokerRateLimitError("Upstox rate limit hit while fetching holdings.")
        if resp.status_code != 200:
            raise BrokerAPIError(f"Upstox holdings fetch failed: {resp.status_code} {resp.text}")

        body = resp.json()
        raw_items = body.get("data", [])
        return [
            RawHolding(
                symbol=item.get("trading_symbol", ""),
                isin=item.get("isin"),
                exchange=item.get("exchange"),
                quantity=float(item.get("quantity", 0)),
                avg_cost_price=(
                    float(item["average_price"]) if item.get("average_price") is not None else None
                ),
            )
            for item in raw_items
        ]

    # ── HTTP boundary — isolated so tests can mock it without live creds ──────

    def _http_post_token(self, auth_code: str, redirect_uri: str) -> requests.Response:
        return requests.post(
            _TOKEN_URL,
            data={
                "code": auth_code,
                "client_id": self._api_key,
                "client_secret": self._api_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
            headers={"Accept": "application/json"},
            timeout=_REQUEST_TIMEOUT_SECONDS,
        )

    def _http_get_holdings(self, access_token: str) -> requests.Response:
        return requests.get(
            _HOLDINGS_URL,
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {access_token}",
            },
            timeout=_REQUEST_TIMEOUT_SECONDS,
        )
