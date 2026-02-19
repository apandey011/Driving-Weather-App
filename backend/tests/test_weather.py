"""Tests for app.services.weather — Open-Meteo API client."""

from datetime import datetime, timezone

import httpx
import pytest
import respx

from app.models import LatLng, Waypoint
from app.services.weather import (
    HOURLY_PARAMS,
    OPEN_METEO_URL,
    WMO_CODES,
    get_weather_for_waypoints,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_wp(
    lat: float = 37.77,
    lng: float = -122.42,
    hour: int = 10,
) -> Waypoint:
    return Waypoint(
        location=LatLng(lat=lat, lng=lng),
        minutes_from_start=0,
        estimated_time=datetime(2026, 2, 16, hour, 0, tzinfo=timezone.utc),
    )


def _hourly_response(
    *,
    hour_count: int = 24,
    temperature: float = 15.0,
    apparent_temp: float = 13.0,
    precipitation: float = 0.0,
    precip_prob: int = 10,
    weather_code: int = 1,
    wind_speed: float = 12.0,
    humidity: int = 65,
) -> dict:
    """Build a mock Open-Meteo hourly response."""
    times = [f"2026-02-16T{h:02d}:00" for h in range(hour_count)]
    return {
        "hourly": {
            "time": times,
            "temperature_2m": [temperature] * hour_count,
            "apparent_temperature": [apparent_temp] * hour_count,
            "precipitation": [precipitation] * hour_count,
            "precipitation_probability": [precip_prob] * hour_count,
            "weather_code": [weather_code] * hour_count,
            "wind_speed_10m": [wind_speed] * hour_count,
            "relative_humidity_2m": [humidity] * hour_count,
        }
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestGetWeatherForWaypoints:
    @pytest.mark.asyncio
    @respx.mock
    async def test_successful_fetch_populates_weather(self):
        respx.get(OPEN_METEO_URL).mock(
            return_value=httpx.Response(200, json=_hourly_response(temperature=18.5))
        )
        wp = _make_wp()
        result = await get_weather_for_waypoints([wp])

        assert result[0].weather is not None
        assert result[0].weather.temperature_c == 18.5

    @pytest.mark.asyncio
    @respx.mock
    async def test_correct_api_params(self):
        route = respx.get(OPEN_METEO_URL).mock(
            return_value=httpx.Response(200, json=_hourly_response())
        )
        wp = _make_wp(lat=37.77, lng=-122.42)
        await get_weather_for_waypoints([wp])

        assert route.called
        request = route.calls[0].request
        url = str(request.url)
        assert "latitude=37.77" in url
        assert "longitude=-122.42" in url
        assert "start_date=2026-02-16" in url
        assert "end_date=2026-02-16" in url
        assert "timezone=auto" in url
        # Check hourly params
        for param in HOURLY_PARAMS:
            assert param in url

    @pytest.mark.asyncio
    @respx.mock
    async def test_uses_nearest_hour_index(self):
        """The hour index should match the waypoint's hour."""
        # Set up different temps for each hour so we can verify the right index
        resp_data = _hourly_response()
        resp_data["hourly"]["temperature_2m"] = list(range(24))  # 0,1,2,...,23
        respx.get(OPEN_METEO_URL).mock(
            return_value=httpx.Response(200, json=resp_data)
        )
        wp = _make_wp(hour=14)
        await get_weather_for_waypoints([wp])

        assert wp.weather is not None
        assert wp.weather.temperature_c == 14.0

    @pytest.mark.asyncio
    @respx.mock
    async def test_hour_capped_at_array_length(self):
        """If hour exceeds array length, use last index."""
        resp_data = _hourly_response(hour_count=12)
        resp_data["hourly"]["temperature_2m"] = list(range(12))
        respx.get(OPEN_METEO_URL).mock(
            return_value=httpx.Response(200, json=resp_data)
        )
        wp = _make_wp(hour=20)  # beyond the 12 entries
        await get_weather_for_waypoints([wp])

        assert wp.weather is not None
        # idx = min(20, 12-1) = 11
        assert wp.weather.temperature_c == 11.0

    @pytest.mark.asyncio
    @respx.mock
    async def test_wmo_code_mapped_to_description(self):
        respx.get(OPEN_METEO_URL).mock(
            return_value=httpx.Response(200, json=_hourly_response(weather_code=45))
        )
        wp = _make_wp()
        await get_weather_for_waypoints([wp])

        assert wp.weather is not None
        assert wp.weather.weather_description == WMO_CODES[45]
        assert wp.weather.weather_description == "Fog"

    @pytest.mark.asyncio
    @respx.mock
    async def test_unknown_wmo_code_returns_unknown(self):
        respx.get(OPEN_METEO_URL).mock(
            return_value=httpx.Response(200, json=_hourly_response(weather_code=999))
        )
        wp = _make_wp()
        await get_weather_for_waypoints([wp])

        assert wp.weather is not None
        assert wp.weather.weather_description == "Unknown"

    @pytest.mark.asyncio
    @respx.mock
    async def test_missing_hourly_key_raises_runtime_error(self):
        """If the response has no 'hourly' key, a RuntimeError should propagate."""
        respx.get(OPEN_METEO_URL).mock(
            return_value=httpx.Response(200, json={"error": True, "reason": "bad request"})
        )
        wp = _make_wp()
        # The error is caught by asyncio.gather(return_exceptions=True) in
        # get_weather_for_waypoints, so weather stays None
        result = await get_weather_for_waypoints([wp])
        assert result[0].weather is None

    @pytest.mark.asyncio
    @respx.mock
    async def test_multiple_waypoints_fetched_in_parallel(self):
        route = respx.get(OPEN_METEO_URL).mock(
            return_value=httpx.Response(200, json=_hourly_response())
        )
        wp1 = _make_wp(lat=37.77, lng=-122.42)
        wp2 = _make_wp(lat=34.05, lng=-118.24)
        wp3 = _make_wp(lat=40.71, lng=-74.01)

        await get_weather_for_waypoints([wp1, wp2, wp3])

        assert route.call_count == 3
        assert wp1.weather is not None
        assert wp2.weather is not None
        assert wp3.weather is not None

    @pytest.mark.asyncio
    @respx.mock
    async def test_one_failure_doesnt_block_others(self):
        """If one waypoint fetch fails, others should still succeed."""
        def responder(request: httpx.Request) -> httpx.Response:
            lat = request.url.params.get("latitude")
            if lat == "34.05":
                return httpx.Response(500, json={"error": "server error"})
            if lat == "37.77":
                return httpx.Response(200, json=_hourly_response(temperature=10.0))
            return httpx.Response(200, json=_hourly_response(temperature=20.0))

        respx.get(OPEN_METEO_URL).mock(side_effect=responder)
        wp1 = _make_wp(lat=37.77, lng=-122.42)
        wp2 = _make_wp(lat=34.05, lng=-118.24)
        wp3 = _make_wp(lat=40.71, lng=-74.01)

        await get_weather_for_waypoints([wp1, wp2, wp3])

        # wp1 and wp3 should have weather; wp2 should not (server returned no hourly)
        assert wp1.weather is not None
        assert wp1.weather.temperature_c == 10.0
        # wp2 got a 500 with no "hourly" key → RuntimeError → weather stays None
        assert wp2.weather is None
        assert wp3.weather is not None
        assert wp3.weather.temperature_c == 20.0
