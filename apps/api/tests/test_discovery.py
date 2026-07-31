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
from app.models.user import User
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

    def _incr(key):
        # Mirrors Redis INCR: absent key starts at 0, so the first call
        # returns 1. Values are stored as strings, as real Redis does.
        store[key] = str(int(store.get(key, 0)) + 1)
        return int(store[key])

    monkeypatch.setattr("app.services.discovery_service.redis_client.set", _set)
    monkeypatch.setattr("app.services.discovery_service.redis_client.incr", _incr)
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


def _make_verified_portfolio(email: str, strategy_slugs: list[str] | None = None) -> Portfolio:
    """Milestone 7: verified portfolios can now carry strategy tags too
    (auto-assigned by sync_service in production; attached directly here to
    test the discovery filter query itself, not the full sync pipeline —
    that's covered in test_sync_service.py)."""
    user = User(email=email, username=email.split("@")[0], password_hash="x")
    db.session.add(user)
    db.session.flush()

    portfolio = Portfolio(user_id=user.id, portfolio_type="verified", is_public=True)
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

    def test_verified_portfolio_with_auto_tag_matches_filter(self, client):
        # Milestone 7 — before this, no verified portfolio could ever match
        # a strategy filter (only manually-curated Public Investor Library
        # entries had tags).
        _make_verified_portfolio("m7-verified-lowrisk@example.com", ["low-risk"])
        _make_public_investor("Growth Investor M7", "growth-investor-m7", ["growth"])

        resp = client.get(f"{INVESTORS_URL}?strategy=low-risk")
        assert resp.status_code == 200
        types = [r["portfolio_type"] for r in resp.get_json()["data"]]
        assert "verified" in types

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

    def test_invalidate_stops_the_cached_entry_being_served(self, client, fake_redis):
        """Invalidation orphans keys rather than deleting them (ADR-045).

        Asserted through behaviour, not key count: what callers are owed is
        that a read after invalidation does not return the pre-invalidation
        entry. The old key lingering until its TTL is an implementation
        detail, and asserting it was gone was really asserting SCAN+DELETE.
        """
        _make_public_investor("Invalidate Test Investor", "invalidate-test-investor")
        client.get(INVESTORS_URL)

        before = [k for k in fake_redis if k.startswith("discovery:investors:")]
        assert len(before) == 1

        invalidate_discovery_cache()
        client.get(INVESTORS_URL)

        after = [k for k in fake_redis if k.startswith("discovery:investors:")]
        new_keys = set(after) - set(before)
        assert new_keys, "post-invalidation read served the stale entry instead of re-querying"

    def test_invalidate_is_one_redis_call_regardless_of_cached_pages(
        self, client, fake_redis, monkeypatch
    ):
        """The point of ADR-045: cost is O(1), not O(cached keys).

        The previous implementation issued a keyspace SCAN plus one DELETE
        per match on *every* sync completion.
        """
        _make_public_investor("Counting Investor", "counting-investor")
        for page in range(1, 4):
            for sort in ("recency", "portfolio_age", "alphabetical"):
                client.get(f"{INVESTORS_URL}?page={page}&sort={sort}")

        cached = [k for k in fake_redis if k.startswith("discovery:investors:")]
        assert len(cached) >= 5, "need several cached pages for this to mean anything"

        calls = []
        real_incr = __import__(
            "app.services.discovery_service", fromlist=["redis_client"]
        ).redis_client.incr

        def counting_incr(key):
            calls.append(key)
            return real_incr(key)

        monkeypatch.setattr("app.services.discovery_service.redis_client.incr", counting_incr)
        invalidate_discovery_cache()

        assert len(calls) == 1, f"expected a single INCR, got {len(calls)} calls"

    def test_cache_version_falls_back_to_1_when_redis_is_down(self, client, monkeypatch):
        """A Redis outage must degrade to uncached, not to a 500."""

        def _boom(*_args, **_kwargs):
            raise ConnectionError("redis is down")

        monkeypatch.setattr("app.services.discovery_service.redis_client.get", _boom)
        monkeypatch.setattr("app.services.discovery_service.redis_client.set", _boom)

        _make_public_investor("Outage Investor", "outage-investor")
        resp = client.get(INVESTORS_URL)
        assert resp.status_code == 200


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
