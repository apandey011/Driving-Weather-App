"""Integration tests for app.routes — the POST /api/route-weather endpoint."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi import HTTPException

from app.main import app
from app.models import (
    LatLng,
    MultiRouteResponse,
    RouteRecommendation,
    RouteScore,
    RouteWithWeather,
    Waypoint,
    WeatherAdvisory,
    WeatherData,
)
from app.services.cache import route_cache


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _sample_route_data() -> dict:
    """Minimal return value for get_routes."""
    return {
        "origin_address": "San Francisco, CA, USA",
        "destination_address": "Los Angeles, CA, USA",
        "routes": [
            {
                "overview_polyline": "abc123",
                "summary": "via I-5 S",
                "total_duration_seconds": 21000,
                "total_distance_meters": 612300,
                "steps": [
                    {
                        "duration_seconds": 21000,
                        "distance_meters": 612300,
                        "start_location": {"lat": 37.77, "lng": -122.42},
                        "end_location": {"lat": 34.05, "lng": -118.24},
                        "polyline": "abc",
                    }
                ],
            }
        ],
    }


def _sample_waypoints() -> list[Waypoint]:
    """Minimal list of waypoints returned by sample_route_points."""
    return [
        Waypoint(
            location=LatLng(lat=37.77, lng=-122.42),
            minutes_from_start=0,
            estimated_time=datetime(2026, 2, 16, 10, 0, tzinfo=timezone.utc),
            weather=None,
        ),
        Waypoint(
            location=LatLng(lat=34.05, lng=-118.24),
            minutes_from_start=350,
            estimated_time=datetime(2026, 2, 16, 15, 50, tzinfo=timezone.utc),
            weather=None,
        ),
    ]


def _sample_recommendation() -> RouteRecommendation:
    return RouteRecommendation(
        recommended_route_index=0,
        scores=[
            RouteScore(
                overall_score=85.0,
                duration_score=90.0,
                weather_score=80.0,
                recommendation_reason="Fastest route with mostly clear weather",
            )
        ],
        advisories=[[]],
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestRouteWeatherEndpoint:
    @pytest.fixture(autouse=True)
    def clear_cache(self):
        """Clear the route cache before each test."""
        route_cache._store.clear()
        yield
        route_cache._store.clear()

    @pytest.mark.asyncio
    async def test_successful_end_to_end(self):
        with (
            patch("app.routes.get_routes", new_callable=AsyncMock) as mock_routes,
            patch("app.routes.sample_route_points") as mock_sample,
            patch("app.routes.get_weather_for_waypoints", new_callable=AsyncMock) as mock_weather,
            patch("app.routes.score_routes", new_callable=AsyncMock) as mock_score,
        ):
            mock_routes.return_value = _sample_route_data()
            mock_sample.return_value = _sample_waypoints()
            mock_weather.return_value = []
            mock_score.return_value = _sample_recommendation()

            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                resp = await client.post(
                    "/api/route-weather",
                    json={
                        "origin": "San Francisco, CA",
                        "destination": "Los Angeles, CA",
                    },
                )

            assert resp.status_code == 200
            data = resp.json()
            assert data["origin_address"] == "San Francisco, CA, USA"
            assert data["destination_address"] == "Los Angeles, CA, USA"

    @pytest.mark.asyncio
    async def test_response_includes_correct_fields(self):
        with (
            patch("app.routes.get_routes", new_callable=AsyncMock) as mock_routes,
            patch("app.routes.sample_route_points") as mock_sample,
            patch("app.routes.get_weather_for_waypoints", new_callable=AsyncMock) as mock_weather,
            patch("app.routes.score_routes", new_callable=AsyncMock) as mock_score,
        ):
            mock_routes.return_value = _sample_route_data()
            mock_sample.return_value = _sample_waypoints()
            mock_weather.return_value = []
            mock_score.return_value = _sample_recommendation()

            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                resp = await client.post(
                    "/api/route-weather",
                    json={
                        "origin": "SF",
                        "destination": "LA",
                    },
                )

            data = resp.json()
            assert "origin_address" in data
            assert "destination_address" in data
            assert "routes" in data
            assert "recommendation" in data
            assert len(data["routes"]) == 1
            route = data["routes"][0]
            assert "overview_polyline" in route
            assert "summary" in route
            assert "total_duration_minutes" in route
            assert "total_distance_km" in route
            assert "waypoints" in route

    @pytest.mark.asyncio
    async def test_cache_hit_returns_cached_response(self):
        """A second identical request should return the cached response."""
        with (
            patch("app.routes.get_routes", new_callable=AsyncMock) as mock_routes,
            patch("app.routes.sample_route_points") as mock_sample,
            patch("app.routes.get_weather_for_waypoints", new_callable=AsyncMock) as mock_weather,
            patch("app.routes.score_routes", new_callable=AsyncMock) as mock_score,
        ):
            mock_routes.return_value = _sample_route_data()
            mock_sample.return_value = _sample_waypoints()
            mock_weather.return_value = []
            mock_score.return_value = _sample_recommendation()

            request_body = {
                "origin": "San Francisco, CA",
                "destination": "Los Angeles, CA",
            }

            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                resp1 = await client.post("/api/route-weather", json=request_body)
                resp2 = await client.post("/api/route-weather", json=request_body)

            assert resp1.status_code == 200
            assert resp2.status_code == 200
            # get_routes should only be called once (second time is cached)
            assert mock_routes.call_count == 1

    @pytest.mark.asyncio
    async def test_http_exception_propagates(self):
        with patch("app.routes.get_routes", new_callable=AsyncMock) as mock_routes:
            mock_routes.side_effect = HTTPException(
                status_code=400,
                detail="Directions API error: ZERO_RESULTS",
            )

            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                resp = await client.post(
                    "/api/route-weather",
                    json={"origin": "Nowhere", "destination": "Nowhere"},
                )

            assert resp.status_code == 400
            assert "ZERO_RESULTS" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_generic_exception_returns_500(self):
        with patch("app.routes.get_routes", new_callable=AsyncMock) as mock_routes:
            mock_routes.side_effect = RuntimeError("Unexpected failure")

            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                resp = await client.post(
                    "/api/route-weather",
                    json={"origin": "SF", "destination": "LA"},
                )

            assert resp.status_code == 500
            assert resp.json()["detail"] == "Internal server error"

    @pytest.mark.asyncio
    async def test_naive_departure_time_returns_422(self):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.post(
                "/api/route-weather",
                json={
                    "origin": "SF",
                    "destination": "LA",
                    "departure_time": "2026-02-16T10:00",
                },
            )

        assert resp.status_code == 422
