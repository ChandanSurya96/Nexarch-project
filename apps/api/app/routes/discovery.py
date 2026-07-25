"""Discovery blueprint.

Endpoints (all under /api/v1/discovery — prefix registered in create_app),
both public/unauthenticated per docs/api.md "Rate Limiting":
    GET /investors            — filterable, paginated, sortable feed
    GET /strategy-categories

See docs/product-requirements.md "Feature: Investor Discovery Feed" — no
"most followed" sort (Phase 2+ only, cold-start reasons).
"""

from flask import Blueprint, request
from marshmallow import ValidationError

from app.schemas.discovery import DiscoveryQuerySchema
from app.schemas.strategy_category import StrategyCategorySchema
from app.services.discovery_service import list_investors, list_strategy_categories
from app.utils.responses import error, success

discovery_bp = Blueprint("discovery", __name__)

_query_schema = DiscoveryQuerySchema()
_category_schema = StrategyCategorySchema()


@discovery_bp.get("/investors")
def get_investors():
    try:
        params = _query_schema.load(request.args.to_dict())
    except ValidationError as exc:
        return error("VALIDATION_ERROR", str(exc.messages), 400)

    results, total = list_investors(
        params["strategy"], params["sort"], params["page"], params["per_page"]
    )
    total_pages = (total + params["per_page"] - 1) // params["per_page"] if total else 0

    return success(
        results,
        meta={
            "pagination": {
                "page": params["page"],
                "per_page": params["per_page"],
                "total": total,
                "total_pages": total_pages,
            }
        },
    )


@discovery_bp.get("/strategy-categories")
def get_strategy_categories():
    categories = list_strategy_categories()
    return success(_category_schema.dump(categories, many=True))
