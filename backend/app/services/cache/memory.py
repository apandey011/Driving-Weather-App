"""In-memory TTL cache with LRU eviction."""

from __future__ import annotations

import time
from collections import OrderedDict
from typing import Any

from .base import BaseRouteCache, DEFAULT_TTL, MAX_ENTRIES


class TTLCache(BaseRouteCache):
    def __init__(self, ttl: int = DEFAULT_TTL, max_entries: int = MAX_ENTRIES):
        self._ttl = ttl
        self._max_entries = max_entries
        self._store: OrderedDict[str, tuple[float, Any]] = OrderedDict()

    def get(self, key: str) -> Any | None:
        if key not in self._store:
            return None
        ts, value = self._store[key]
        if time.time() - ts > self._ttl:
            del self._store[key]
            return None
        self._store.move_to_end(key)
        return value

    def set(self, key: str, value: Any) -> None:
        if key in self._store:
            self._store.move_to_end(key)
        self._store[key] = (time.time(), value)
        while len(self._store) > self._max_entries:
            self._store.popitem(last=False)

    def clear(self) -> None:
        self._store.clear()
