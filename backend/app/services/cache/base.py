"""Shared cache interface and key semantics."""

from __future__ import annotations

import hashlib
import json
from abc import ABC, abstractmethod
from typing import Any

DEFAULT_TTL = 30 * 60  # 30 minutes
MAX_ENTRIES = 100


def make_cache_key(origin: str, destination: str, departure_time_iso: str | None) -> str:
    dt_rounded = ""
    if departure_time_iso:
        dt_rounded = departure_time_iso[:13]  # "2026-02-16T10"
    raw = json.dumps(
        [origin.lower().strip(), destination.lower().strip(), dt_rounded],
        sort_keys=True,
    )
    return hashlib.sha256(raw.encode()).hexdigest()


class BaseRouteCache(ABC):
    @staticmethod
    def make_key(origin: str, destination: str, departure_time_iso: str | None) -> str:
        return make_cache_key(origin, destination, departure_time_iso)

    @abstractmethod
    def get(self, key: str) -> Any | None:
        raise NotImplementedError

    @abstractmethod
    def set(self, key: str, value: Any) -> None:
        raise NotImplementedError

    @abstractmethod
    def clear(self) -> None:
        raise NotImplementedError

    def close(self) -> None:
        return
