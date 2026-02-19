from typing import Literal

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    google_maps_api_key: str
    frontend_origin: str = "http://localhost:5173"
    log_format: Literal["plain", "json"] = "plain"
    route_weather_rate_limit: str = "30/minute"
    sentry_dsn_backend: str | None = None
    sentry_environment: str = "development"
    sentry_release: str | None = None
    cache_backend: Literal["memory", "redis"] = "memory"
    redis_url: str | None = None

    model_config = {"env_file": ".env"}


settings = Settings()
