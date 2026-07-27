"""
Flask extensions are instantiated here (without a bound app) and imported
everywhere. The actual app binding happens in create_app() via init_app(),
which is the standard Flask app-factory pattern.
"""

import redis
from flask_bcrypt import Bcrypt
from flask_jwt_extended import JWTManager, get_jwt_identity, verify_jwt_in_request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
jwt = JWTManager()
bcrypt = Bcrypt()
migrate = Migrate()


def _rate_limit_key() -> str:
    """Per-user for authenticated requests, per-IP otherwise (docs/api.md
    "Rate Limiting"). Flask-Limiter's key function runs before a route's own
    @jwt_required() decorator, so the JWT hasn't been verified yet at this
    point — verify_jwt_in_request(optional=True) does that verification here
    (cheap: flask-jwt-extended caches the decode in `g`, so the route's own
    decorator afterward is nearly free) and falls back to the IP when there's
    no valid token at all (e.g. /auth/login, /auth/register, public routes).
    """
    try:
        verify_jwt_in_request(optional=True)
        identity = get_jwt_identity()
    except Exception:
        identity = None
    return identity or get_remote_address()


limiter = Limiter(key_func=_rate_limit_key, default_limits=["100 per minute"])


class RedisClient:
    """Thin wrapper so redis_client can be imported and used the same way
    as the other extensions above — unbound at import time, bound via
    init_app() once REDIS_URL is available from app.config.

    Used for the discovery-feed cache (see docs/architecture.md "Caching
    Strategy"); redis-py connects lazily, so constructing this in
    create_app() doesn't require Redis to already be reachable.
    """

    def __init__(self) -> None:
        self._client: redis.Redis | None = None

    def init_app(self, app) -> None:
        # Explicit short timeouts (redis-py defaults to None = block
        # forever): without these, a blackholed connection — dropped
        # packets, not an active refusal, the classic network-partition
        # case — can hang for minutes rather than failing fast. Matters
        # here and for the /health/ready readiness probe (ADR-034), which
        # would otherwise be only as reliable as an unbounded socket call.
        self._client = redis.Redis.from_url(
            app.config["REDIS_URL"],
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
        )

    def get(self, key: str) -> str | None:
        return self._client.get(key)

    def set(self, key: str, value: str, ex: int | None = None) -> None:
        self._client.set(key, value, ex=ex)

    def delete(self, key: str) -> None:
        self._client.delete(key)

    def scan_delete(self, pattern: str) -> None:
        """Delete every key matching pattern — used for cache invalidation
        on sync completion."""
        for key in self._client.scan_iter(match=pattern):
            self._client.delete(key)

    def ping(self) -> bool:
        """Used by GET /health/ready (ADR-034) — raises on an unreachable
        server rather than returning False, same as the underlying
        redis-py client; the route catches it."""
        return self._client.ping()


redis_client = RedisClient()
