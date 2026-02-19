"""Tests for app.services.directions — Google Directions API client."""

import httpx
import pytest
import respx
from fastapi import HTTPException

from app.services.directions import DIRECTIONS_URL, get_routes


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _directions_response(
    *,
    status: str = "OK",
    routes: list[dict] | None = None,
) -> dict:
    """Build a mock Google Directions API response."""
    if routes is None:
        routes = [
            {
                "summary": "via I-5 S",
                "overview_polyline": {"points": "abc123"},
                "legs": [
                    {
                        "start_address": "San Francisco, CA, USA",
                        "end_address": "Los Angeles, CA, USA",
                        "steps": [
                            {
                                "duration": {"value": 600},
                                "distance": {"value": 5000},
                                "start_location": {"lat": 37.77, "lng": -122.42},
                                "end_location": {"lat": 36.00, "lng": -120.00},
                                "polyline": {"points": "abc"},
                            },
                            {
                                "duration": {"value": 900},
                                "distance": {"value": 8000},
                                "start_location": {"lat": 36.00, "lng": -120.00},
                                "end_location": {"lat": 34.05, "lng": -118.24},
                                "polyline": {"points": "def"},
                            },
                        ],
                    }
                ],
            }
        ]
    return {"status": status, "routes": routes}


def _multi_leg_response() -> dict:
    """Response with multiple legs (waypoints) and multiple routes."""
    return {
        "status": "OK",
        "routes": [
            {
                "summary": "Route A",
                "overview_polyline": {"points": "polyA"},
                "legs": [
                    {
                        "start_address": "Origin City",
                        "end_address": "Mid City",
                        "steps": [
                            {
                                "duration": {"value": 300},
                                "distance": {"value": 2000},
                                "start_location": {"lat": 37.0, "lng": -122.0},
                                "end_location": {"lat": 36.0, "lng": -121.0},
                                "polyline": {"points": "s1"},
                            },
                        ],
                    },
                    {
                        "start_address": "Mid City",
                        "end_address": "Destination City",
                        "steps": [
                            {
                                "duration": {"value": 500},
                                "distance": {"value": 3000},
                                "start_location": {"lat": 36.0, "lng": -121.0},
                                "end_location": {"lat": 35.0, "lng": -120.0},
                                "polyline": {"points": "s2"},
                            },
                        ],
                    },
                ],
            },
            {
                "summary": "Route B",
                "overview_polyline": {"points": "polyB"},
                "legs": [
                    {
                        "start_address": "Origin City",
                        "end_address": "Destination City",
                        "steps": [
                            {
                                "duration": {"value": 1000},
                                "distance": {"value": 7000},
                                "start_location": {"lat": 37.0, "lng": -122.0},
                                "end_location": {"lat": 35.0, "lng": -120.0},
                                "polyline": {"points": "s3"},
                            },
                        ],
                    },
                ],
            },
        ],
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestGetRoutes:
    @pytest.mark.asyncio
    @respx.mock
    async def test_successful_response_extracts_routes(self):
        respx.get(DIRECTIONS_URL).mock(
            return_value=httpx.Response(200, json=_directions_response())
        )
        result = await get_routes("San Francisco", "Los Angeles")

        assert "routes" in result
        assert len(result["routes"]) == 1
        route = result["routes"][0]
        assert route["summary"] == "via I-5 S"
        assert route["overview_polyline"] == "abc123"

    @pytest.mark.asyncio
    @respx.mock
    async def test_steps_flattened_from_multiple_legs(self):
        respx.get(DIRECTIONS_URL).mock(
            return_value=httpx.Response(200, json=_multi_leg_response())
        )
        result = await get_routes("Origin", "Destination")

        # Route A has 2 legs with 1 step each = 2 steps total
        route_a = result["routes"][0]
        assert len(route_a["steps"]) == 2
        assert route_a["steps"][0]["duration_seconds"] == 300
        assert route_a["steps"][1]["duration_seconds"] == 500

    @pytest.mark.asyncio
    @respx.mock
    async def test_total_duration_and_distance_are_sums(self):
        respx.get(DIRECTIONS_URL).mock(
            return_value=httpx.Response(200, json=_directions_response())
        )
        result = await get_routes("SF", "LA")

        route = result["routes"][0]
        # 600 + 900 = 1500 seconds
        assert route["total_duration_seconds"] == 1500
        # 5000 + 8000 = 13000 meters
        assert route["total_distance_meters"] == 13000

    @pytest.mark.asyncio
    @respx.mock
    async def test_origin_destination_addresses_extracted(self):
        respx.get(DIRECTIONS_URL).mock(
            return_value=httpx.Response(200, json=_directions_response())
        )
        result = await get_routes("SF", "LA")

        assert result["origin_address"] == "San Francisco, CA, USA"
        assert result["destination_address"] == "Los Angeles, CA, USA"

    @pytest.mark.asyncio
    @respx.mock
    async def test_non_ok_status_raises_http_exception(self):
        respx.get(DIRECTIONS_URL).mock(
            return_value=httpx.Response(200, json=_directions_response(status="ZERO_RESULTS"))
        )
        with pytest.raises(HTTPException) as exc_info:
            await get_routes("Nowhere", "Nowhere Else")

        assert exc_info.value.status_code == 400
        assert "ZERO_RESULTS" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    @respx.mock
    async def test_missing_summary_defaults_to_empty_string(self):
        resp = _directions_response()
        # Remove the "summary" key from the first route
        del resp["routes"][0]["summary"]
        respx.get(DIRECTIONS_URL).mock(
            return_value=httpx.Response(200, json=resp)
        )
        result = await get_routes("SF", "LA")

        assert result["routes"][0]["summary"] == ""

    @pytest.mark.asyncio
    @respx.mock
    async def test_empty_routes_raises_404(self):
        respx.get(DIRECTIONS_URL).mock(
            return_value=httpx.Response(
                200, json=_directions_response(routes=[])
            )
        )
        with pytest.raises(HTTPException) as exc_info:
            await get_routes("SF", "LA")

        assert exc_info.value.status_code == 404
        assert "No routes found" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    @respx.mock
    async def test_multiple_routes_returned(self):
        respx.get(DIRECTIONS_URL).mock(
            return_value=httpx.Response(200, json=_multi_leg_response())
        )
        result = await get_routes("Origin", "Destination")

        assert len(result["routes"]) == 2
        assert result["routes"][0]["summary"] == "Route A"
        assert result["routes"][1]["summary"] == "Route B"
