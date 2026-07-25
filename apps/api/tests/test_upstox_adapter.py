"""Tests for the Upstox adapter — all HTTP calls mocked, no live credentials.

See docs/development-guide.md "Testing Strategy": broker adapters must be
testable against recorded/mocked responses, not live broker accounts.
"""

from unittest.mock import MagicMock, patch

import pytest

from app.integrations.broker.base import (
    BrokerAPIError,
    BrokerAuthError,
    BrokerRateLimitError,
    BrokerTokenExpiredError,
)
from app.integrations.broker.upstox import UpstoxAdapter


def _mock_response(status_code: int, json_body: dict):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_body
    resp.text = str(json_body)
    return resp


class TestGetLoginUrl:
    def test_contains_redirect_uri(self, monkeypatch):
        monkeypatch.setenv("UPSTOX_API_KEY", "test-client-id")
        adapter = UpstoxAdapter()
        url = adapter.get_login_url("http://localhost:3000/broker-callback")
        assert "client_id=test-client-id" in url
        assert "redirect_uri=http://localhost:3000/broker-callback" in url


class TestExchangeCode:
    def test_success(self):
        adapter = UpstoxAdapter()
        with patch.object(
            adapter,
            "_http_post_token",
            return_value=_mock_response(
                200, {"access_token": "acc-123", "extended_token": "ext-456"}
            ),
        ):
            tokens = adapter.exchange_code("auth-code", "http://localhost:3000/broker-callback")

        assert tokens.access_token == "acc-123"
        assert tokens.refresh_token == "ext-456"
        assert tokens.expires_at is not None

    def test_failure_raises_broker_auth_error(self):
        adapter = UpstoxAdapter()
        with patch.object(
            adapter, "_http_post_token", return_value=_mock_response(400, {"error": "bad code"})
        ):
            with pytest.raises(BrokerAuthError):
                adapter.exchange_code("bad-code", "http://localhost:3000/broker-callback")

    def test_missing_access_token_raises(self):
        adapter = UpstoxAdapter()
        with patch.object(adapter, "_http_post_token", return_value=_mock_response(200, {})):
            with pytest.raises(BrokerAuthError):
                adapter.exchange_code("auth-code", "http://localhost:3000/broker-callback")


class TestFetchHoldings:
    def test_success(self):
        adapter = UpstoxAdapter()
        body = {
            "data": [
                {
                    "trading_symbol": "RELIANCE",
                    "isin": "INE002A01018",
                    "exchange": "NSE",
                    "quantity": 10,
                    "average_price": 2500.5,
                }
            ]
        }
        with patch.object(adapter, "_http_get_holdings", return_value=_mock_response(200, body)):
            holdings = adapter.fetch_holdings("acc-123")

        assert len(holdings) == 1
        assert holdings[0].symbol == "RELIANCE"
        assert holdings[0].isin == "INE002A01018"
        assert holdings[0].quantity == 10.0
        assert holdings[0].avg_cost_price == 2500.5

    def test_expired_token_raises_distinct_error(self):
        adapter = UpstoxAdapter()
        with patch.object(adapter, "_http_get_holdings", return_value=_mock_response(401, {})):
            with pytest.raises(BrokerTokenExpiredError):
                adapter.fetch_holdings("expired-token")

    def test_rate_limit_raises_distinct_error(self):
        adapter = UpstoxAdapter()
        with patch.object(adapter, "_http_get_holdings", return_value=_mock_response(429, {})):
            with pytest.raises(BrokerRateLimitError):
                adapter.fetch_holdings("acc-123")

    def test_other_failure_raises_generic_api_error(self):
        adapter = UpstoxAdapter()
        with patch.object(adapter, "_http_get_holdings", return_value=_mock_response(500, {})):
            with pytest.raises(BrokerAPIError):
                adapter.fetch_holdings("acc-123")

    def test_empty_holdings_list(self):
        adapter = UpstoxAdapter()
        with patch.object(
            adapter, "_http_get_holdings", return_value=_mock_response(200, {"data": []})
        ):
            holdings = adapter.fetch_holdings("acc-123")
        assert holdings == []
