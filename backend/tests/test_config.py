"""Tests for app.config — Settings loading from environment variables."""

import os
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from app.config import Settings


class TestSettings:
    def test_loads_from_env(self):
        """Settings should load values from environment variables."""
        with patch.dict(os.environ, {
            "GOOGLE_MAPS_API_KEY": "my-test-key",
            "FRONTEND_ORIGIN": "http://example.com",
        }):
            s = Settings()
        assert s.google_maps_api_key == "my-test-key"
        assert s.frontend_origin == "http://example.com"

    def test_frontend_origin_default(self):
        """frontend_origin should default to http://localhost:5173."""
        with patch.dict(os.environ, {
            "GOOGLE_MAPS_API_KEY": "some-key",
        }, clear=False):
            # Remove FRONTEND_ORIGIN if present
            env = os.environ.copy()
            env.pop("FRONTEND_ORIGIN", None)
            with patch.dict(os.environ, env, clear=True):
                s = Settings()
        assert s.frontend_origin == "http://localhost:5173"
        assert s.log_format == "plain"
        assert s.route_weather_rate_limit == "30/minute"
        assert s.cache_backend == "memory"

    def test_missing_api_key_raises_validation_error(self):
        """If GOOGLE_MAPS_API_KEY is not set (and no .env file), Settings() should raise."""
        # Temporarily override the model_config to prevent reading .env file,
        # and clear the environment of the key.
        env = os.environ.copy()
        env.pop("GOOGLE_MAPS_API_KEY", None)
        env.pop("FRONTEND_ORIGIN", None)
        with patch.dict(os.environ, env, clear=True):
            # Patch the env_file setting so pydantic-settings does not read .env
            with patch.object(Settings, "model_config", {"env_file": None}):
                with pytest.raises(ValidationError):
                    Settings()
