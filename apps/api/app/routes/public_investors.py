"""Public Investors blueprint.

Endpoints (all under /api/v1/public-investors — prefix registered in
create_app), both public/unauthenticated per docs/api.md "Rate Limiting":
    GET /            — list
    GET /:slug       — detail

See docs/product-requirements.md "Feature: Public Investor Library".
"""

from flask import Blueprint

from app.schemas.public_investor import PublicInvestorSchema
from app.services.public_investor_service import get_by_slug, list_public_investors
from app.utils.responses import error, success

public_investors_bp = Blueprint("public_investors", __name__)

_investor_schema = PublicInvestorSchema()


@public_investors_bp.get("")
def list_investors():
    investors = list_public_investors()
    return success(_investor_schema.dump(investors, many=True))


@public_investors_bp.get("/<slug>")
def get_investor(slug: str):
    investor = get_by_slug(slug)
    if investor is None:
        return error("PUBLIC_INVESTOR_NOT_FOUND", "Public investor not found.", 404)

    return success(_investor_schema.dump(investor))
