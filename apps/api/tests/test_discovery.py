"""Tests for /api/v1/discovery/*.

Redis is faked here (an in-memory dict standing in for redis_client) so this
suite doesn't need a live Redis server, per the project's existing "no live
external dependency" testing philosophy (see docs/development-guide.md).
"""

import pytest

from app.extensions import db
from app.models.portfolio import Portfolio
from app.models.public_investor import PublicInvestor
from app.models.strategy_category import PortfolioStrategyTag, StrategyCategory
from app.services.discovery_service import invalidate_discovery_cache

REGISTER_URL = "/api/v1/auth/register"
LOGIN_URL = "/api/v1/auth/login"
INVESTORS_URL = "/api/v1/discovery/investors"
CATEGORIES_URL = "/api/v1/discovery/strategy-categories"


@pytest.fixture(autouse=True)
def fake_redis(monkeypatch):
    store: dict[str, str] = {}
    monkeypatch.setattr("app.services.discovery_service.redis_client.get", store.get)

    def _set(key, value, ex=None):
        store[key] = value

    def _scan_delete(pattern):
        prefix = pattern.rstrip("*")
        for key in [k for k in store if k.startswith(prefix)]:
            del store[key]

    monkeypatch.setattr("app.services.discovery_service.redis_client.set", _set)
    monkeypatch.setattr("app.services.discovery_service.redis_client.scan_delete", _scan_delete)
    return store


def _make_public_investor(
    name: str, slug: str, strategy_slugs: list[str] | None = None
) -> Portfolio:
    investor = PublicInvestor(name=name, slug=slug)
    db.session.add(investor)
    db.session.flush()

    portfolio = Portfolio(public_investor_id=investor.id, portfolio_type="public", is_public=True)
    db.session.add(portfolio)
    db.session.flush()

    for slug_ in strategy_slugs or []:
        category = StrategyCategory.query.filter_by(slug=slug_).first()
        if category is None:
            category = StrategyCategory(name=slug_.title(), slug=slug_, description="test")
            db.session.add(category)
            db.session.flush()
        db.session.add(
            PortfolioStrategyTag(portfolio_id=portfolio.id, strategy_category_id=category.id)
        )

    db.session.commit()
    return portfolio


class TestListInvestors:
    def test_only_public_portfolios_returned(self, client):
        _make_public_investor("Investor A", "investor-a")
        private_investor = PublicInvestor(name="Hidden", slug="hidden")
        db.session.add(private_investor)
        db.session.flush()
        db.session.add(
            Portfolio(
                public_investor_id=private_investor.id, portfolio_type="public", is_public=False
            )
        )
        db.session.commit()

        resp = client.get(INVESTORS_URL)
        assert resp.status_code == 200
        names = [r["display_name"] for r in resp.get_json()["data"]]
        assert "Investor A" in names
        assert "Hidden" not in names

    def test_filter_by_strategy(self, client):
        _make_public_investor("Value Investor", "value-investor", ["value"])
        _make_public_investor("Growth Investor", "growth-investor", ["growth"])

        resp = client.get(f"{INVESTORS_URL}?strategy=value")
        assert resp.status_code == 200
        names = [r["display_name"] for r in resp.get_json()["data"]]
        assert names == ["Value Investor"]

    def test_sort_alphabetical(self, client):
        _make_public_investor("Zebra Capital", "zebra-capital")
        _make_public_investor("Alpha Capital", "alpha-capital")

        resp = client.get(f"{INVESTORS_URL}?sort=alphabetical")
        names = [r["display_name"] for r in resp.get_json()["data"]]
        assert names.index("Alpha Capital") < names.index("Zebra Capital")

    def test_pagination_meta(self, client):
        for i in range(5):
            _make_public_investor(f"Investor {i}", f"investor-{i}")

        # Compared against the DB's own count rather than a hard-coded total:
        # app-level db.session.commit() calls (including inside the helper
        # above) don't roll back between tests the way flush-only changes
        # do, so other tests' seeded portfolios can still be present here —
        # this assertion only cares that pagination math is internally
        # consistent, not that this test's 5 rows are the only ones in the DB.
        expected_total = Portfolio.query.filter_by(is_public=True).count()

        resp = client.get(f"{INVESTORS_URL}?per_page=2&page=1")
        body = resp.get_json()
        assert len(body["data"]) == 2
        assert body["meta"]["pagination"]["total"] == expected_total
        assert body["meta"]["pagination"]["total_pages"] == (expected_total + 1) // 2

    def test_invalid_sort_returns_400(self, client):
        resp = client.get(f"{INVESTORS_URL}?sort=most_followed")
        assert resp.status_code == 400
        assert resp.get_json()["error"]["code"] == "VALIDATION_ERROR"

    def test_result_is_cached(self, client, fake_redis):
        _make_public_investor("Cache Test Investor", "cache-test-investor")
        client.get(INVESTORS_URL)
        assert any(key.startswith("discovery:investors:") for key in fake_redis)

    def test_invalidate_clears_cache(self, client, fake_redis):
        _make_public_investor("Invalidate Test Investor", "invalidate-test-investor")
        client.get(INVESTORS_URL)
        assert len(fake_redis) > 0

        invalidate_discovery_cache()
        assert len(fake_redis) == 0


class TestStrategyCategories:
    def test_list_categories(self, client):
        # get-or-create: other tests' committed categories don't roll back
        # between tests (see the note in test_pagination_meta above), so a
        # "value" row may already exist here.
        if StrategyCategory.query.filter_by(slug="value").first() is None:
            db.session.add(StrategyCategory(name="Value", slug="value", description="test"))
            db.session.commit()

        resp = client.get(CATEGORIES_URL)
        assert resp.status_code == 200
        slugs = [c["slug"] for c in resp.get_json()["data"]]
        assert "value" in slugs
