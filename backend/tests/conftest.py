"""Shared fixtures for the Route Weather backend test suite."""

import os

# Set required env vars BEFORE any app imports so that
# ``app.config.Settings()`` (which runs at import time) succeeds.
os.environ.setdefault("GOOGLE_MAPS_API_KEY", "test-api-key-12345")
os.environ.setdefault("FRONTEND_ORIGIN", "http://localhost:5173")

from datetime import datetime, timezone

from app.models import (
    LatLng,
    RouteWithWeather,
    Waypoint,
    WeatherData,
)


# ---------------------------------------------------------------------------
# Factory helpers
# ---------------------------------------------------------------------------


def make_weather(
    *,
    temperature_c: float = 15.0,
    apparent_temperature_c: float = 13.0,
    precipitation_mm: float = 0.0,
    precipitation_probability: int = 10,
    weather_code: int = 1,
    weather_description: str = "Mainly clear",
    wind_speed_kmh: float = 10.0,
    humidity_percent: int = 65,
) -> WeatherData:
    return WeatherData(
        temperature_c=temperature_c,
        apparent_temperature_c=apparent_temperature_c,
        precipitation_mm=precipitation_mm,
        precipitation_probability=precipitation_probability,
        weather_code=weather_code,
        weather_description=weather_description,
        wind_speed_kmh=wind_speed_kmh,
        humidity_percent=humidity_percent,
    )


def make_waypoint(
    *,
    lat: float = 37.77,
    lng: float = -122.42,
    minutes_from_start: int = 0,
    estimated_time: datetime | None = None,
    weather: WeatherData | None = None,
) -> Waypoint:
    if estimated_time is None:
        estimated_time = datetime(2026, 2, 16, 10, 0, tzinfo=timezone.utc)
    return Waypoint(
        location=LatLng(lat=lat, lng=lng),
        minutes_from_start=minutes_from_start,
        estimated_time=estimated_time,
        weather=weather,
    )


def make_route(
    *,
    route_index: int = 0,
    overview_polyline: str = "abc",
    summary: str = "via I-5 S",
    total_duration_minutes: int = 350,
    total_distance_km: float = 612.3,
    waypoints: list[Waypoint] | None = None,
) -> RouteWithWeather:
    if waypoints is None:
        waypoints = [make_waypoint(weather=make_weather())]
    return RouteWithWeather(
        route_index=route_index,
        overview_polyline=overview_polyline,
        summary=summary,
        total_duration_minutes=total_duration_minutes,
        total_distance_km=total_distance_km,
        waypoints=waypoints,
    )
