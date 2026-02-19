"""Route cache facade with pluggable backend selection."""

from __future__ import annotations

import logging
from typing import Any

from ...config import settings
from .base import BaseRouteCache
from .memory import TTLCache
from .redis import RedisRouteCache

logger = logging.getLogger(__name__)


def _build_cache_backend() -> BaseRouteCache:
    if settings.cache_backend == "redis":
        if not settings.redis_url:
            logger.warning("CACHE_BACKEND=redis but REDIS_URL is not set. Falling back to memory cache.")
            return TTLCache()
        try:
            redis_cache = RedisRouteCache(settings.redis_url)
            redis_cache.ping()
            logger.info("Using redis route cache backend.")
            return redis_cache
        except Exception as exc:
            logger.warning("Redis cache unavailable (%s). Falling back to memory cache.", exc)
            return TTLCache()

    return TTLCache()


class RouteCacheManager(BaseRouteCache):
    def __init__(self):
        self._backend: BaseRouteCache = TTLCache()

    @property
    def backend_name(self) -> str:
        return self._backend.__class__.__name__

    @property
    def backend(self) -> BaseRouteCache:
        return self._backend

    def configure(self) -> None:
        old_backend = self._backend
        self._backend = _build_cache_backend()
        if old_backend is not self._backend:
            old_backend.close()

    def get(self, key: str) -> Any | None:
        return self._backend.get(key)

    def set(self, key: str, value: Any) -> None:
        self._backend.set(key, value)

    def clear(self) -> None:
        self._backend.clear()

    def close(self) -> None:
        self._backend.close()


route_cache = RouteCacheManager()
route_cache.configure()

__all__ = [
    "BaseRouteCache",
    "RedisRouteCache",
    "RouteCacheManager",
    "TTLCache",
    "route_cache",
]
