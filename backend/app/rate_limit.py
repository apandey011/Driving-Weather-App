from __future__ import annotations

from typing import Callable

try:
    from slowapi import Limiter
    from slowapi.errors import RateLimitExceeded
    from slowapi.util import get_remote_address

    SLOWAPI_AVAILABLE = True
    limiter = Limiter(key_func=get_remote_address, default_limits=[])
except ModuleNotFoundError:  # pragma: no cover
    SLOWAPI_AVAILABLE = False

    class RateLimitExceeded(Exception):
        pass

    class _DummyStorage:
        def reset(self) -> None:
            return

    class _DummyLimiter:
        _storage = _DummyStorage()

        def limit(self, _limit: str) -> Callable:
            def decorator(func: Callable) -> Callable:
                return func

            return decorator

    limiter = _DummyLimiter()
