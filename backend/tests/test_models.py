"""Tests for app.models — Pydantic model validation."""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.models import (
    LatLng,
    MultiRouteResponse,
    RouteRecommendation,
    RouteRequest,
    RouteScore,
    RouteWithWeather,
    Waypoint,
    WeatherAdvisory,
    WeatherData,
)


# ---------------------------------------------------------------------------
# RouteRequest
# ---------------------------------------------------------------------------


class TestRouteRequest:
    def test_valid_minimal(self):
        req = RouteRequest(origin="SF", destination="LA")
        assert req.origin == "SF"
        assert req.destination == "LA"
        assert req.departure_time is None

    def test_with_departure_time(self):
        dt = datetime(2026, 2, 16, 10, 0, tzinfo=timezone.utc)
        req = RouteRequest(origin="SF", destination="LA", departure_time=dt)
        assert req.departure_time == dt

    def test_missing_origin_raises_validation_error(self):
        with pytest.raises(ValidationError):
            RouteRequest(destination="LA")

    def test_missing_destination_raises_validation_error(self):
        with pytest.raises(ValidationError):
            RouteRequest(origin="SF")

    def test_naive_datetime_raises_validation_error(self):
        with pytest.raises(ValidationError):
            RouteRequest(
                origin="SF",
                destination="LA",
                departure_time=datetime(2026, 2, 16, 10, 0),
            )


# ---------------------------------------------------------------------------
# Waypoint
# ---------------------------------------------------------------------------


class TestWaypoint:
    def test_weather_defaults_to_none(self):
        wp = Waypoint(
            location=LatLng(lat=37.77, lng=-122.42),
            minutes_from_start=0,
            estimated_time=datetime(2026, 2, 16, 10, 0, tzinfo=timezone.utc),
        )
        assert wp.weather is None

    def test_weather_can_be_set(self):
        wd = WeatherData(
            temperature_c=15.0,
            apparent_temperature_c=13.0,
            precipitation_mm=0.0,
            precipitation_probability=10,
            weather_code=1,
            weather_description="Mainly clear",
            wind_speed_kmh=10.0,
            humidity_percent=65,
        )
        wp = Waypoint(
            location=LatLng(lat=37.77, lng=-122.42),
            minutes_from_start=0,
            estimated_time=datetime(2026, 2, 16, 10, 0, tzinfo=timezone.utc),
            weather=wd,
        )
        assert wp.weather is not None
        assert wp.weather.temperature_c == 15.0


# ---------------------------------------------------------------------------
# MultiRouteResponse
# ---------------------------------------------------------------------------


class TestMultiRouteResponse:
    def test_recommendation_defaults_to_none(self):
        resp = MultiRouteResponse(
            origin_address="SF",
            destination_address="LA",
            routes=[],
        )
        assert resp.recommendation is None

    def test_with_recommendation(self):
        rec = RouteRecommendation(
            recommended_route_index=0,
            scores=[
                RouteScore(
                    overall_score=85.0,
                    duration_score=90.0,
                    weather_score=80.0,
                    recommendation_reason="Good route",
                )
            ],
            advisories=[[]],
        )
        resp = MultiRouteResponse(
            origin_address="SF",
            destination_address="LA",
            routes=[],
            recommendation=rec,
        )
        assert resp.recommendation is not None
        assert resp.recommendation.recommended_route_index == 0


# ---------------------------------------------------------------------------
# WeatherData
# ---------------------------------------------------------------------------


class TestWeatherData:
    def test_valid_weather_data(self):
        wd = WeatherData(
            temperature_c=15.0,
            apparent_temperature_c=13.0,
            precipitation_mm=0.0,
            precipitation_probability=10,
            weather_code=1,
            weather_description="Mainly clear",
            wind_speed_kmh=10.0,
            humidity_percent=65,
        )
        assert wd.temperature_c == 15.0

    def test_missing_field_raises_validation_error(self):
        with pytest.raises(ValidationError):
            WeatherData(
                temperature_c=15.0,
                # missing required fields
            )


# ---------------------------------------------------------------------------
# RouteWithWeather
# ---------------------------------------------------------------------------


class TestRouteWithWeather:
    def test_valid_route(self):
        route = RouteWithWeather(
            route_index=0,
            overview_polyline="abc",
            summary="via I-5",
            total_duration_minutes=350,
            total_distance_km=612.3,
            waypoints=[],
        )
        assert route.route_index == 0
        assert route.total_duration_minutes == 350

    def test_missing_field_raises_validation_error(self):
        with pytest.raises(ValidationError):
            RouteWithWeather(
                route_index=0,
                # missing required fields
            )


# ---------------------------------------------------------------------------
# WeatherAdvisory
# ---------------------------------------------------------------------------


class TestWeatherAdvisory:
    def test_valid_advisory(self):
        adv = WeatherAdvisory(
            type="heavy_rain",
            severity="danger",
            message="Heavy rain expected near SF",
        )
        assert adv.severity == "danger"

    def test_warning_severity(self):
        adv = WeatherAdvisory(
            type="fog",
            severity="warning",
            message="Fog near SF",
        )
        assert adv.severity == "warning"

    def test_invalid_severity_raises_validation_error(self):
        with pytest.raises(ValidationError):
            WeatherAdvisory(
                type="rain",
                severity="info",
                message="Some rain",
            )

    def test_missing_field_raises_validation_error(self):
        with pytest.raises(ValidationError):
            WeatherAdvisory(type="rain")
