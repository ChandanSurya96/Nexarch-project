"""Tests for app/services/activity_service.py (ADR-015)."""

import uuid
from datetime import date

from app.extensions import db
from app.models.portfolio import Portfolio
from app.services.activity_service import get_activity


def _add_snapshot(portfolio_id, snapshot_date, sector_allocation, holding_count):
    from app.models.portfolio_snapshot import PortfolioSnapshot

    snapshot = PortfolioSnapshot(
        portfolio_id=portfolio_id,
        snapshot_date=snapshot_date,
        sector_allocation=sector_allocation,
        health_metrics={"holding_count": holding_count},
    )
    db.session.add(snapshot)
    db.session.commit()
    return snapshot


class TestGetActivity:
    def test_fewer_than_two_snapshots_returns_empty(self, client):
        user_resp = client.post(
            "/api/v1/auth/register",
            json={
                "email": "activity1@example.com",
                "password": "Secure123",
                "username": "activity1",
            },
        )
        user_id = uuid.UUID(user_resp.get_json()["data"]["user_id"])
        portfolio = Portfolio(user_id=user_id, portfolio_type="verified", is_public=True)
        db.session.add(portfolio)
        db.session.commit()

        assert get_activity(portfolio.id) == []

        _add_snapshot(portfolio.id, date(2026, 7, 18), {"Financials": 1.0}, 3)
        assert get_activity(portfolio.id) == []

    def test_meaningful_sector_change_produces_entry(self, client):
        user_resp = client.post(
            "/api/v1/auth/register",
            json={
                "email": "activity2@example.com",
                "password": "Secure123",
                "username": "activity2",
            },
        )
        user_id = uuid.UUID(user_resp.get_json()["data"]["user_id"])
        portfolio = Portfolio(user_id=user_id, portfolio_type="verified", is_public=True)
        db.session.add(portfolio)
        db.session.commit()

        _add_snapshot(portfolio.id, date(2026, 7, 18), {"Financials": 0.31, "IT": 0.24}, 3)
        _add_snapshot(portfolio.id, date(2026, 7, 25), {"Financials": 0.28, "IT": 0.27}, 3)

        activity = get_activity(portfolio.id)
        assert len(activity) == 1
        entry = activity[0]
        assert entry["from_date"] == "2026-07-18"
        assert entry["to_date"] == "2026-07-25"
        assert {"sector": "Financials", "before": 0.31, "after": 0.28} in entry["sector_changes"]
        assert "Financials" in entry["summary"]
        assert entry["holding_count_change"] is None

    def test_negligible_change_produces_no_entry(self, client):
        user_resp = client.post(
            "/api/v1/auth/register",
            json={
                "email": "activity3@example.com",
                "password": "Secure123",
                "username": "activity3",
            },
        )
        user_id = uuid.UUID(user_resp.get_json()["data"]["user_id"])
        portfolio = Portfolio(user_id=user_id, portfolio_type="verified", is_public=True)
        db.session.add(portfolio)
        db.session.commit()

        _add_snapshot(portfolio.id, date(2026, 7, 18), {"Financials": 0.500}, 3)
        _add_snapshot(portfolio.id, date(2026, 7, 25), {"Financials": 0.503}, 3)

        assert get_activity(portfolio.id) == []

    def test_holding_count_change_detected(self, client):
        user_resp = client.post(
            "/api/v1/auth/register",
            json={
                "email": "activity4@example.com",
                "password": "Secure123",
                "username": "activity4",
            },
        )
        user_id = uuid.UUID(user_resp.get_json()["data"]["user_id"])
        portfolio = Portfolio(user_id=user_id, portfolio_type="verified", is_public=True)
        db.session.add(portfolio)
        db.session.commit()

        _add_snapshot(portfolio.id, date(2026, 7, 18), {"Financials": 1.0}, 3)
        _add_snapshot(portfolio.id, date(2026, 7, 25), {"Financials": 1.0}, 4)

        activity = get_activity(portfolio.id)
        assert len(activity) == 1
        assert activity[0]["holding_count_change"] == {"before": 3, "after": 4}
        assert "holding count" in activity[0]["summary"]

    def test_most_recent_first(self, client):
        user_resp = client.post(
            "/api/v1/auth/register",
            json={
                "email": "activity5@example.com",
                "password": "Secure123",
                "username": "activity5",
            },
        )
        user_id = uuid.UUID(user_resp.get_json()["data"]["user_id"])
        portfolio = Portfolio(user_id=user_id, portfolio_type="verified", is_public=True)
        db.session.add(portfolio)
        db.session.commit()

        _add_snapshot(portfolio.id, date(2026, 7, 1), {"Financials": 1.0}, 1)
        _add_snapshot(portfolio.id, date(2026, 7, 10), {"Financials": 1.0}, 2)
        _add_snapshot(portfolio.id, date(2026, 7, 20), {"Financials": 1.0}, 3)

        activity = get_activity(portfolio.id)
        assert len(activity) == 2
        assert activity[0]["from_date"] == "2026-07-10"  # most recent diff first
        assert activity[1]["from_date"] == "2026-07-01"
