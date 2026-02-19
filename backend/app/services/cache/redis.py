"""Redis-backed cache implementation."""

from __future__ import annotations

import json
import logging
from typing import Any

from .base import BaseRouteCache, DEFAULT_TTL

try:
    import redis
except ModuleNotFoundError:  # pragma: no cover - exercised via fallback tests
    redis = None

from ...models import MultiRouteResponse

logger = logging.getLogger(__name__)


class RedisRouteCache(BaseRouteCache):
    def __init__(self, redis_url: str, ttl: int = DEFAULT_TTL):
        if redis is None:
            raise RuntimeError("redis package is not installed")
        self._ttl = ttl
        self._client = redis.Redis.from_url(
            redis_url,
            socket_timeout=1,
            socket_connect_timeout=1,
            health_check_interval=30,
        )

    def ping(self) -> None:
        self._client.ping()

    def get(self, key: str) -> Any | None:
        raw = self._client.get(key)
        if raw is None:
            return None
        payload = raw.decode() if isinstance(raw, (bytes, bytearray)) else raw
        try:
            data = json.loads(payload)
            return MultiRouteResponse.model_validate(data)
        except Exception:
            logger.warning("Failed to decode cached value for key %s", key)
            return None

    def set(self, key: str, value: Any) -> None:
        if hasattr(value, "model_dump"):
            payload = json.dumps(value.model_dump(mode="json"))
        else:
            payload = json.dumps(value, default=str)
        self._client.setex(key, self._ttl, payload)

    def clear(self) -> None:
        self._client.flushdb()

    def close(self) -> None:
        self._client.close()
