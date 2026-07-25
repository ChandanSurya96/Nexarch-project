"""Tests for /api/v1/portfolios/*.

Portfolios are created directly via the ORM here (not through the broker
connect flow) since these tests target the read/visibility/update logic in
isolation from sync — see test_broker_connections.py for the connect->sync path.
"""

import uuid
from datetime import UTC, date, datetime

from app.extensions import db
from app.models.holding import Holding
from app.models.portfolio import Portfolio
from app.models.portfolio_snapshot import PortfolioSnapshot

REGISTER_URL = "/api/v1/auth/register"
LOGIN_URL = "/api/v1/auth/login"


def _register_and_login(client, email, username):
    payload = {"email": email, "password": "Secure123", "username": username}
    reg_resp = client.post(REGISTER_URL, json=payload)
    user_id = reg_resp.get_json()["data"]["user_id"]
    login_resp = client.post(LOGIN_URL, json={"email": email, "password": payload["password"]})
    access_token = login_resp.get_json()["data"]["access_token"]
    return uuid.UUID(user_id), access_token


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _make_portfolio(user_id: uuid.UUID, is_public: bool) -> Portfolio:
    portfolio = Portfolio(user_id=user_id, portfolio_type="verified", is_public=is_public)
    db.session.add(portfolio)
    db.session.commit()
    return portfolio


class TestGetPortfolio:
    def test_public_portfolio_visible_without_auth(self, client):
        user_id, _ = _register_and_login(client, "pub-owner@example.com", "pubowner")
        portfolio = _make_portfolio(user_id, is_public=True)

        resp = client.get(f"/api/v1/portfolios/{portfolio.id}")
        assert resp.status_code == 200
        assert resp.get_json()["data"]["is_public"] is True

    def test_private_portfolio_hidden_from_non_owner(self, client):
        user_id, _ = _register_and_login(client, "priv-owner@example.com", "privowner")
        portfolio = _make_portfolio(user_id, is_public=False)

        _, other_token = _register_and_login(client, "stranger@example.com", "stranger")
        resp = client.get(f"/api/v1/portfolios/{portfolio.id}", headers=_auth_header(other_token))
        assert resp.status_code == 404
        assert resp.get_json()["error"]["code"] == "PORTFOLIO_NOT_FOUND"

    def test_private_portfolio_hidden_from_anonymous(self, client):
        user_id, _ = _register_and_login(client, "priv-owner2@example.com", "privowner2")
        portfolio = _make_portfolio(user_id, is_public=False)

        resp = client.get(f"/api/v1/portfolios/{portfolio.id}")
        assert resp.status_code == 404

    def test_private_portfolio_visible_to_owner(self, client):
        user_id, token = _register_and_login(client, "priv-owner3@example.com", "privowner3")
        portfolio = _make_portfolio(user_id, is_public=False)

        resp = client.get(f"/api/v1/portfolios/{portfolio.id}", headers=_auth_header(token))
        assert resp.status_code == 200

    def test_nonexistent_portfolio_returns_404(self, client):
        resp = client.get(f"/api/v1/portfolios/{uuid.uuid4()}")
        assert resp.status_code == 404


class TestGetHoldings:
    def test_returns_holdings_for_public_portfolio(self, client):
        user_id, _ = _register_and_login(client, "holdings-owner@example.com", "holdingsowner")
        portfolio = _make_portfolio(user_id, is_public=True)
        holding = Holding(
            portfolio_id=portfolio.id,
            symbol="RELIANCE",
            isin="INE002A01018",
            exchange="NSE",
            quantity=10,
            avg_cost_price=2500,
            sector="Energy",
            market_cap_category="large",
            as_of_date=date(2026, 7, 25),
        )
        db.session.add(holding)
        db.session.commit()

        resp = client.get(f"/api/v1/portfolios/{portfolio.id}/holdings")
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert len(data) == 1
        assert data[0]["symbol"] == "RELIANCE"

    def test_private_holdings_hidden_from_non_owner(self, client):
        user_id, _ = _register_and_login(client, "holdings-priv@example.com", "holdingspriv")
        portfolio = _make_portfolio(user_id, is_public=False)

        resp = client.get(f"/api/v1/portfolios/{portfolio.id}/holdings")
        assert resp.status_code == 404


class TestGetAnalytics:
    def test_no_snapshot_yet_returns_honestly_empty(self, client):
        user_id, _ = _register_and_login(client, "analytics-empty@example.com", "analyticsempty")
        portfolio = _make_portfolio(user_id, is_public=True)

        resp = client.get(f"/api/v1/portfolios/{portfolio.id}/analytics")
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data["total_value"] is None
        assert data["health"] is None
        assert data["sector_allocation"] == {}

    def test_with_snapshot_returns_health_metrics(self, client):
        user_id, _ = _register_and_login(client, "analytics-full@example.com", "analyticsfull")
        portfolio = _make_portfolio(user_id, is_public=True)
        snapshot = PortfolioSnapshot(
            portfolio_id=portfolio.id,
            snapshot_date=date(2026, 7, 25),
            total_value=25000,
            sector_allocation={"Energy": 1.0},
            asset_allocation={"Equity": 1.0},
            health_metrics={
                "diversification_score": 0.0,
                "sector_concentration_hhi": 1.0,
                "portfolio_age_days": 0,
                "holding_count": 1,
                "volatility": None,
            },
        )
        db.session.add(snapshot)
        db.session.commit()

        resp = client.get(f"/api/v1/portfolios/{portfolio.id}/analytics")
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data["total_value"] == 25000.0
        assert data["sector_allocation"] == {"Energy": 1.0}
        assert data["health"]["sector_concentration_hhi"] == 1.0
        assert data["as_of"] == "2026-07-25"
        # No composite score (ADR-007); volatility present but honestly None
        # here since this snapshot was hand-built without price data (ADR-024).
        assert "score" not in data["health"]
        assert data["health"]["volatility"] is None


class TestPatchPortfolio:
    def test_owner_can_toggle_is_public(self, client):
        user_id, token = _register_and_login(client, "patch-owner@example.com", "patchowner")
        portfolio = _make_portfolio(user_id, is_public=False)

        resp = client.patch(
            f"/api/v1/portfolios/{portfolio.id}",
            json={"is_public": True},
            headers=_auth_header(token),
        )
        assert resp.status_code == 200
        assert resp.get_json()["data"]["is_public"] is True

    def test_non_owner_cannot_toggle(self, client):
        user_id, _ = _register_and_login(client, "patch-owner2@example.com", "patchowner2")
        portfolio = _make_portfolio(user_id, is_public=False)

        _, other_token = _register_and_login(client, "patch-stranger@example.com", "patchstranger")
        resp = client.patch(
            f"/api/v1/portfolios/{portfolio.id}",
            json={"is_public": True},
            headers=_auth_header(other_token),
        )
        assert resp.status_code == 404

    def test_requires_auth(self, client):
        user_id, _ = _register_and_login(client, "patch-owner3@example.com", "patchowner3")
        portfolio = _make_portfolio(user_id, is_public=False)

        resp = client.patch(f"/api/v1/portfolios/{portfolio.id}", json={"is_public": True})
        assert resp.status_code == 401

    def test_missing_is_public_field(self, client):
        user_id, token = _register_and_login(client, "patch-owner4@example.com", "patchowner4")
        portfolio = _make_portfolio(user_id, is_public=False)

        resp = client.patch(
            f"/api/v1/portfolios/{portfolio.id}", json={}, headers=_auth_header(token)
        )
        assert resp.status_code == 400


class TestCompleteProfile:
    """GET /portfolios/:id/profile — new, additive endpoint powered by
    PortfolioProfileService.get_complete_profile. Combines the same data the
    four separate endpoints already return; these tests confirm the
    combination is correct, not the underlying computations (those are
    covered by test_analytics_service.py / test_activity_service.py /
    test_strategy_overview_service.py)."""

    def test_happy_path_combines_all_sections(self, client):
        user_id, _ = _register_and_login(client, "profile-owner@example.com", "profileowner")
        portfolio = _make_portfolio(user_id, is_public=True)
        holding = Holding(
            portfolio_id=portfolio.id,
            symbol="RELIANCE",
            isin="INE002A01018",
            exchange="NSE",
            quantity=10,
            avg_cost_price=2500,
            sector="Energy",
            market_cap_category="large",
            as_of_date=date(2026, 7, 25),
        )
        db.session.add(holding)
        snapshot = PortfolioSnapshot(
            portfolio_id=portfolio.id,
            snapshot_date=date(2026, 7, 25),
            total_value=25000,
            sector_allocation={"Energy": 1.0},
            asset_allocation={"Equity": 1.0},
            health_metrics={
                "diversification_score": 0.0,
                "sector_concentration_hhi": 1.0,
                "portfolio_age_days": 0,
                "holding_count": 1,
            },
        )
        db.session.add(snapshot)
        db.session.commit()

        resp = client.get(f"/api/v1/portfolios/{portfolio.id}/profile")
        assert resp.status_code == 200
        data = resp.get_json()["data"]

        assert data["portfolio"]["id"] == str(portfolio.id)
        assert len(data["holdings"]) == 1
        assert data["holdings"][0]["symbol"] == "RELIANCE"
        assert data["analytics"]["health"]["sector_concentration_hhi"] == 1.0
        assert data["analytics"]["strategy_overview"] is not None
        assert data["activity"] == []  # only one snapshot — no diff yet

    def test_no_snapshot_yet_is_honestly_empty(self, client):
        user_id, _ = _register_and_login(client, "profile-empty@example.com", "profileempty")
        portfolio = _make_portfolio(user_id, is_public=True)

        resp = client.get(f"/api/v1/portfolios/{portfolio.id}/profile")
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data["holdings"] == []
        assert data["analytics"]["total_value"] is None
        assert data["analytics"]["health"] is None
        assert data["activity"] == []

    def test_private_portfolio_returns_404(self, client):
        user_id, _ = _register_and_login(client, "profile-priv@example.com", "profilepriv")
        portfolio = _make_portfolio(user_id, is_public=False)

        resp = client.get(f"/api/v1/portfolios/{portfolio.id}/profile")
        assert resp.status_code == 404
        assert resp.get_json()["error"]["code"] == "PORTFOLIO_NOT_FOUND"

    def test_owner_can_view_own_private_profile(self, client):
        user_id, token = _register_and_login(client, "profile-owner2@example.com", "profileowner2")
        portfolio = _make_portfolio(user_id, is_public=False)

        resp = client.get(f"/api/v1/portfolios/{portfolio.id}/profile", headers=_auth_header(token))
        assert resp.status_code == 200


class TestGetHistory:
    def test_no_snapshots_yet_returns_empty_list(self, client):
        user_id, _ = _register_and_login(client, "history-empty@example.com", "historyempty")
        portfolio = _make_portfolio(user_id, is_public=True)

        resp = client.get(f"/api/v1/portfolios/{portfolio.id}/history")
        assert resp.status_code == 200
        assert resp.get_json()["data"] == []

    def test_returns_snapshots_oldest_to_newest(self, client):
        user_id, _ = _register_and_login(client, "history-owner@example.com", "historyowner")
        portfolio = _make_portfolio(user_id, is_public=True)

        older = PortfolioSnapshot(
            portfolio_id=portfolio.id,
            snapshot_date=date(2026, 7, 1),
            total_value=20000,
            sector_allocation={"Energy": 1.0},
            asset_allocation={"Equity": 1.0},
            health_metrics={
                "diversification_score": 0.0,
                "sector_concentration_hhi": 1.0,
                "portfolio_age_days": 0,
                "holding_count": 1,
                "volatility": None,
            },
        )
        newer = PortfolioSnapshot(
            portfolio_id=portfolio.id,
            snapshot_date=date(2026, 7, 25),
            total_value=25000,
            sector_allocation={"Energy": 1.0},
            asset_allocation={"Equity": 1.0},
            health_metrics={
                "diversification_score": 0.0,
                "sector_concentration_hhi": 1.0,
                "portfolio_age_days": 24,
                "holding_count": 1,
                "volatility": 0.182,
            },
        )
        db.session.add_all([older, newer])
        db.session.commit()

        resp = client.get(f"/api/v1/portfolios/{portfolio.id}/history")
        assert resp.status_code == 200
        data = resp.get_json()["data"]

        assert len(data) == 2
        assert data[0]["snapshot_date"] == "2026-07-01"
        assert data[0]["total_value"] == 20000.0
        assert data[0]["volatility"] is None
        assert data[1]["snapshot_date"] == "2026-07-25"
        assert data[1]["volatility"] == 0.182

    def test_private_portfolio_returns_404(self, client):
        user_id, _ = _register_and_login(client, "history-priv@example.com", "historypriv")
        portfolio = _make_portfolio(user_id, is_public=False)

        resp = client.get(f"/api/v1/portfolios/{portfolio.id}/history")
        assert resp.status_code == 404
        assert resp.get_json()["error"]["code"] == "PORTFOLIO_NOT_FOUND"


class TestSnapshotOrdering:
    """ADR-025 — snapshot_date isn't unique per portfolio (more than one
    sync can land on the same calendar date), so created_at is what makes
    "latest" and chronological ordering deterministic."""

    def _same_day_snapshots(self, portfolio_id: uuid.UUID) -> tuple[PortfolioSnapshot, PortfolioSnapshot]:
        same_day = date(2026, 7, 25)
        # The chronologically LATER snapshot is constructed (and added to
        # the session) FIRST, deliberately — this proves the ordering fix
        # depends on created_at, not on insertion/row order.
        later = PortfolioSnapshot(
            portfolio_id=portfolio_id,
            snapshot_date=same_day,
            total_value=30000,
            sector_allocation={"IT": 1.0},
            asset_allocation={"Equity": 1.0},
            health_metrics={
                "diversification_score": 0.0,
                "sector_concentration_hhi": 1.0,
                "portfolio_age_days": 0,
                "holding_count": 2,
                "volatility": 0.20,
            },
            created_at=datetime(2026, 7, 25, 18, 0, tzinfo=UTC),
        )
        earlier = PortfolioSnapshot(
            portfolio_id=portfolio_id,
            snapshot_date=same_day,
            total_value=25000,
            sector_allocation={"Energy": 1.0},
            asset_allocation={"Equity": 1.0},
            health_metrics={
                "diversification_score": 0.0,
                "sector_concentration_hhi": 1.0,
                "portfolio_age_days": 0,
                "holding_count": 1,
                "volatility": None,
            },
            created_at=datetime(2026, 7, 25, 9, 0, tzinfo=UTC),
        )
        return later, earlier

    def test_analytics_deterministically_returns_the_latest_created_at(self, client):
        user_id, _ = _register_and_login(
            client, "ordering-analytics@example.com", "orderinganalytics"
        )
        portfolio = _make_portfolio(user_id, is_public=True)
        later, earlier = self._same_day_snapshots(portfolio.id)
        db.session.add_all([later, earlier])  # later inserted first, on purpose
        db.session.commit()

        resp = client.get(f"/api/v1/portfolios/{portfolio.id}/analytics")
        assert resp.status_code == 200
        data = resp.get_json()["data"]

        # The 18:00 snapshot is the true latest despite being added first —
        # proves selection is by created_at, not insertion order.
        assert data["total_value"] == 30000.0
        assert data["health"]["holding_count"] == 2
        assert data["health"]["volatility"] == 0.20

    def test_history_includes_both_same_day_snapshots_in_creation_order(self, client):
        user_id, _ = _register_and_login(
            client, "ordering-history@example.com", "orderinghistory"
        )
        portfolio = _make_portfolio(user_id, is_public=True)
        later, earlier = self._same_day_snapshots(portfolio.id)
        db.session.add_all([later, earlier])
        db.session.commit()

        resp = client.get(f"/api/v1/portfolios/{portfolio.id}/history")
        assert resp.status_code == 200
        data = resp.get_json()["data"]

        same_day_entries = [e for e in data if e["snapshot_date"] == "2026-07-25"]
        assert len(same_day_entries) == 2
        # Oldest-created-first within the same date.
        assert same_day_entries[0]["total_value"] == 25000.0
        assert same_day_entries[1]["total_value"] == 30000.0
