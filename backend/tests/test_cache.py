"""Tests for app.services.cache — TTLCache with OrderedDict."""

from unittest.mock import patch

from app.services.cache import RouteCacheManager, TTLCache


# ---------------------------------------------------------------------------
# make_key
# ---------------------------------------------------------------------------


class TestMakeKey:
    def test_deterministic(self):
        """Same inputs always produce the same key."""
        k1 = TTLCache.make_key("SF", "LA", "2026-02-16T10:00:00Z")
        k2 = TTLCache.make_key("SF", "LA", "2026-02-16T10:00:00Z")
        assert k1 == k2

    def test_normalizes_case_and_whitespace(self):
        """Origin/destination are lowercased and stripped."""
        k1 = TTLCache.make_key("  SF  ", "  LA  ", None)
        k2 = TTLCache.make_key("sf", "la", None)
        assert k1 == k2

    def test_rounds_time_to_hour(self):
        """Only the date+hour portion of departure_time matters ([:13])."""
        k1 = TTLCache.make_key("SF", "LA", "2026-02-16T10:00:00Z")
        k2 = TTLCache.make_key("SF", "LA", "2026-02-16T10:59:59Z")
        assert k1 == k2

    def test_different_inputs_differ(self):
        """Distinct logical inputs produce distinct keys."""
        k1 = TTLCache.make_key("SF", "LA", "2026-02-16T10:00:00Z")
        k2 = TTLCache.make_key("LA", "SF", "2026-02-16T10:00:00Z")
        k3 = TTLCache.make_key("SF", "LA", "2026-02-16T11:00:00Z")
        assert k1 != k2
        assert k1 != k3

    def test_handles_none_departure(self):
        """None departure_time is handled without error."""
        k1 = TTLCache.make_key("SF", "LA", None)
        k2 = TTLCache.make_key("SF", "LA", "2026-02-16T10:00:00Z")
        assert isinstance(k1, str)
        assert len(k1) == 64  # SHA-256 hex digest
        assert k1 != k2


# ---------------------------------------------------------------------------
# get
# ---------------------------------------------------------------------------


class TestGet:
    def test_returns_none_for_missing_key(self):
        cache = TTLCache(ttl=60)
        assert cache.get("nonexistent") is None

    def test_returns_value_within_ttl(self):
        cache = TTLCache(ttl=60)
        cache.set("k", "val")
        assert cache.get("k") == "val"

    def test_returns_none_after_ttl_expired(self):
        cache = TTLCache(ttl=60)
        # Pretend set happened at t=1000
        with patch("app.services.cache.memory.time") as mock_time:
            mock_time.time.return_value = 1000.0
            cache.set("k", "val")

        # Now it's t=1061 (>60s TTL)
        with patch("app.services.cache.memory.time") as mock_time:
            mock_time.time.return_value = 1061.0
            assert cache.get("k") is None

        # Key should have been evicted
        assert "k" not in cache._store

    def test_lru_move_to_end_on_access(self):
        cache = TTLCache(ttl=300, max_entries=5)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("c", 3)

        # Access "a" so it moves to the end
        cache.get("a")

        keys = list(cache._store.keys())
        assert keys[-1] == "a"
        assert keys[0] == "b"


# ---------------------------------------------------------------------------
# set
# ---------------------------------------------------------------------------


class TestSet:
    def test_overwrites_existing_value(self):
        cache = TTLCache(ttl=60)
        cache.set("k", "v1")
        cache.set("k", "v2")
        assert cache.get("k") == "v2"

    def test_evicts_oldest_at_capacity(self):
        cache = TTLCache(ttl=300, max_entries=3)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("c", 3)
        cache.set("d", 4)  # should evict "a"

        assert cache.get("a") is None
        assert cache.get("d") == 4
        assert len(cache._store) == 3

    def test_updates_position_on_overwrite(self):
        cache = TTLCache(ttl=300, max_entries=5)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("c", 3)

        # Overwrite "a" — it should move to the end
        cache.set("a", 100)

        keys = list(cache._store.keys())
        assert keys[-1] == "a"
        assert keys[0] == "b"


class TestRouteCacheManager:
    def test_defaults_to_memory_backend(self, monkeypatch):
        monkeypatch.setattr("app.services.cache.settings.cache_backend", "memory")
        manager = RouteCacheManager()
        manager.configure()
        assert manager.backend_name == "TTLCache"

    def test_redis_failure_falls_back_to_memory(self, monkeypatch):
        monkeypatch.setattr("app.services.cache.settings.cache_backend", "redis")
        monkeypatch.setattr("app.services.cache.settings.redis_url", "redis://localhost:6379/0")
        with patch("app.services.cache.RedisRouteCache", side_effect=RuntimeError("redis down")):
            manager = RouteCacheManager()
            manager.configure()
        assert manager.backend_name == "TTLCache"
