"""Tests for /api/v1/public-investors/*."""

from app.extensions import db
from app.models.portfolio import Portfolio
from app.models.public_investor import PublicInvestor

LIST_URL = "/api/v1/public-investors"


class TestListPublicInvestors:
    def test_list_returns_all(self, client):
        db.session.add(PublicInvestor(name="Test Investor", slug="test-investor", bio="bio"))
        db.session.commit()

        resp = client.get(LIST_URL)
        assert resp.status_code == 200
        slugs = [i["slug"] for i in resp.get_json()["data"]]
        assert "test-investor" in slugs

    def test_portfolio_id_is_null_when_not_yet_linked(self, client):
        db.session.add(PublicInvestor(name="No Portfolio Yet", slug="no-portfolio-yet"))
        db.session.commit()

        resp = client.get(LIST_URL)
        entry = next(i for i in resp.get_json()["data"] if i["slug"] == "no-portfolio-yet")
        assert entry["portfolio_id"] is None

    def test_portfolio_id_resolves_when_linked(self, client):
        investor = PublicInvestor(name="Has Portfolio", slug="has-portfolio")
        db.session.add(investor)
        db.session.flush()
        portfolio = Portfolio(
            public_investor_id=investor.id, portfolio_type="public", is_public=True
        )
        db.session.add(portfolio)
        db.session.commit()

        resp = client.get(LIST_URL)
        entry = next(i for i in resp.get_json()["data"] if i["slug"] == "has-portfolio")
        assert entry["portfolio_id"] == str(portfolio.id)


class TestGetPublicInvestor:
    def test_get_by_slug(self, client):
        db.session.add(
            PublicInvestor(
                name="Test Investor",
                slug="test-investor-2",
                bio="bio",
                source_disclosure_url="https://example.com/filing",
            )
        )
        db.session.commit()

        resp = client.get(f"{LIST_URL}/test-investor-2")
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data["name"] == "Test Investor"
        assert data["source_disclosure_url"] == "https://example.com/filing"

    def test_unknown_slug_returns_404(self, client):
        resp = client.get(f"{LIST_URL}/does-not-exist")
        assert resp.status_code == 404
        assert resp.get_json()["error"]["code"] == "PUBLIC_INVESTOR_NOT_FOUND"
