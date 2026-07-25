"""
Flask extensions are instantiated here (without a bound app) and imported
everywhere. The actual app binding happens in create_app() via init_app(),
which is the standard Flask app-factory pattern.
"""

import redis
from flask_bcrypt import Bcrypt
from flask_jwt_extended import JWTManager
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
jwt = JWTManager()
bcrypt = Bcrypt()
migrate = Migrate()


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
        self._client = redis.Redis.from_url(app.config["REDIS_URL"], decode_responses=True)

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


redis_client = RedisClient()
