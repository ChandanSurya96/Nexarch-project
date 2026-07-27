"""Tests for follow/unfollow (POST/DELETE /portfolios/:id/follow) and
GET /users/me/following."""

import uuid

from app.extensions import db
from app.models.follow import Follow
from app.models.portfolio import Portfolio

REGISTER_URL = "/api/v1/auth/register"
LOGIN_URL = "/api/v1/auth/login"
FOLLOWING_URL = "/api/v1/users/me/following"


def _register_and_login(client, email, username):
    payload = {"email": email, "password": "Secure123", "username": username}
    reg_resp = client.post(REGISTER_URL, json=payload)
    user_id = reg_resp.get_json()["data"]["user_id"]
    login_resp = client.post(LOGIN_URL, json={"email": email, "password": payload["password"]})
    token = login_resp.get_json()["data"]["access_token"]
    return uuid.UUID(user_id), token


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _make_portfolio(owner_user_id: uuid.UUID, is_public: bool) -> Portfolio:
    portfolio = Portfolio(user_id=owner_user_id, portfolio_type="verified", is_public=is_public)
    db.session.add(portfolio)
    db.session.commit()
    return portfolio


class TestFollow:
    def test_follow_public_portfolio(self, client):
        owner_id, _ = _register_and_login(client, "follow-owner@example.com", "followowner")
        portfolio = _make_portfolio(owner_id, is_public=True)

        _, follower_token = _register_and_login(client, "follower@example.com", "follower1")
        resp = client.post(
            f"/api/v1/portfolios/{portfolio.id}/follow", headers=_auth_header(follower_token)
        )
        assert resp.status_code == 201
        assert resp.get_json()["data"]["followed"] is True

    def test_follow_is_idempotent_no_duplicate_rows(self, client):
        owner_id, _ = _register_and_login(client, "follow-owner2@example.com", "followowner2")
        portfolio = _make_portfolio(owner_id, is_public=True)

        _, follower_token = _register_and_login(client, "follower2@example.com", "follower2")
        headers = _auth_header(follower_token)
        client.post(f"/api/v1/portfolios/{portfolio.id}/follow", headers=headers)
        client.post(f"/api/v1/portfolios/{portfolio.id}/follow", headers=headers)

        assert Follow.query.filter_by(followed_portfolio_id=portfolio.id).count() == 1

    def test_follow_private_portfolio_returns_404(self, client):
        owner_id, _ = _register_and_login(client, "follow-owner3@example.com", "followowner3")
        portfolio = _make_portfolio(owner_id, is_public=False)

        _, follower_token = _register_and_login(client, "follower3@example.com", "follower3")
        resp = client.post(
            f"/api/v1/portfolios/{portfolio.id}/follow", headers=_auth_header(follower_token)
        )
        assert resp.status_code == 404
        assert resp.get_json()["error"]["code"] == "PORTFOLIO_NOT_FOUND"

    def test_follow_requires_auth(self, client):
        owner_id, _ = _register_and_login(client, "follow-owner4@example.com", "followowner4")
        portfolio = _make_portfolio(owner_id, is_public=True)

        resp = client.post(f"/api/v1/portfolios/{portfolio.id}/follow")
        assert resp.status_code == 401

    def test_cannot_follow_own_portfolio(self, client):
        owner_id, owner_token = _register_and_login(client, "follow-self@example.com", "followself")
        portfolio = _make_portfolio(owner_id, is_public=True)

        resp = client.post(
            f"/api/v1/portfolios/{portfolio.id}/follow", headers=_auth_header(owner_token)
        )
        assert resp.status_code == 400
        assert resp.get_json()["error"]["code"] == "CANNOT_FOLLOW_OWN_PORTFOLIO"
        assert Follow.query.filter_by(followed_portfolio_id=portfolio.id).count() == 0


class TestUnfollow:
    def test_unfollow_removes_follow(self, client):
        owner_id, _ = _register_and_login(client, "unfollow-owner@example.com", "unfollowowner")
        portfolio = _make_portfolio(owner_id, is_public=True)

        _, follower_token = _register_and_login(client, "unfollower@example.com", "unfollower1")
        headers = _auth_header(follower_token)
        client.post(f"/api/v1/portfolios/{portfolio.id}/follow", headers=headers)

        resp = client.delete(f"/api/v1/portfolios/{portfolio.id}/follow", headers=headers)
        assert resp.status_code == 200
        assert resp.get_json()["data"]["followed"] is False
        assert Follow.query.filter_by(followed_portfolio_id=portfolio.id).count() == 0

    def test_unfollow_not_following_is_a_noop(self, client):
        owner_id, _ = _register_and_login(client, "unfollow-owner2@example.com", "unfollowowner2")
        portfolio = _make_portfolio(owner_id, is_public=True)

        _, follower_token = _register_and_login(client, "unfollower2@example.com", "unfollower2")
        resp = client.delete(
            f"/api/v1/portfolios/{portfolio.id}/follow", headers=_auth_header(follower_token)
        )
        assert resp.status_code == 200


class TestListFollowing:
    def test_lists_only_callers_follows(self, client):
        owner_id, _ = _register_and_login(client, "list-owner@example.com", "listowner")
        portfolio_a = _make_portfolio(owner_id, is_public=True)
        portfolio_b = _make_portfolio(owner_id, is_public=True)

        _, follower_token = _register_and_login(client, "lister@example.com", "lister1")
        headers = _auth_header(follower_token)
        client.post(f"/api/v1/portfolios/{portfolio_a.id}/follow", headers=headers)

        resp = client.get(FOLLOWING_URL, headers=headers)
        assert resp.status_code == 200
        ids = [p["id"] for p in resp.get_json()["data"]]
        assert str(portfolio_a.id) in ids
        assert str(portfolio_b.id) not in ids

    def test_following_requires_auth(self, client):
        resp = client.get(FOLLOWING_URL)
        assert resp.status_code == 401


class TestListFollowingPagination:
    def test_pagination_meta_reflects_total_and_per_page(self, client):
        owner_id, _ = _register_and_login(client, "page-owner@example.com", "pageowner")
        portfolios = [_make_portfolio(owner_id, is_public=True) for _ in range(3)]

        _, follower_token = _register_and_login(client, "pager@example.com", "pager1")
        headers = _auth_header(follower_token)
        for p in portfolios:
            client.post(f"/api/v1/portfolios/{p.id}/follow", headers=headers)

        resp = client.get(f"{FOLLOWING_URL}?per_page=2", headers=headers)
        assert resp.status_code == 200
        body = resp.get_json()
        assert len(body["data"]) == 2
        assert body["meta"]["pagination"] == {
            "page": 1,
            "per_page": 2,
            "total": 3,
            "total_pages": 2,
        }

    def test_second_page_returns_the_remainder(self, client):
        owner_id, _ = _register_and_login(client, "page-owner2@example.com", "pageowner2")
        portfolios = [_make_portfolio(owner_id, is_public=True) for _ in range(3)]

        _, follower_token = _register_and_login(client, "pager2@example.com", "pager2")
        headers = _auth_header(follower_token)
        for p in portfolios:
            client.post(f"/api/v1/portfolios/{p.id}/follow", headers=headers)

        resp = client.get(f"{FOLLOWING_URL}?per_page=2&page=2", headers=headers)
        assert resp.status_code == 200
        body = resp.get_json()
        assert len(body["data"]) == 1
        assert body["meta"]["pagination"]["page"] == 2

    def test_page_past_the_end_returns_an_empty_list_not_an_error(self, client):
        owner_id, _ = _register_and_login(client, "page-owner3@example.com", "pageowner3")
        portfolio = _make_portfolio(owner_id, is_public=True)

        _, follower_token = _register_and_login(client, "pager3@example.com", "pager3")
        headers = _auth_header(follower_token)
        client.post(f"/api/v1/portfolios/{portfolio.id}/follow", headers=headers)

        resp = client.get(f"{FOLLOWING_URL}?page=99", headers=headers)
        assert resp.status_code == 200
        assert resp.get_json()["data"] == []

    def test_per_page_over_the_max_is_rejected(self, client):
        _, follower_token = _register_and_login(client, "pager4@example.com", "pager4")
        resp = client.get(f"{FOLLOWING_URL}?per_page=101", headers=_auth_header(follower_token))
        assert resp.status_code == 400
        assert resp.get_json()["error"]["code"] == "VALIDATION_ERROR"

    def test_page_zero_is_rejected(self, client):
        _, follower_token = _register_and_login(client, "pager5@example.com", "pager5")
        resp = client.get(f"{FOLLOWING_URL}?page=0", headers=_auth_header(follower_token))
        assert resp.status_code == 400
        assert resp.get_json()["error"]["code"] == "VALIDATION_ERROR"
