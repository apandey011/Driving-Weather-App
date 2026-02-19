"""Tests for app.services.scoring — feature extraction, advisories, scoring."""

from unittest.mock import AsyncMock, patch

import pytest
from app.services.scoring import (
    _check_advisory_conditions,
    _generate_reason,
    extract_features,
    score_routes,
)
from tests.conftest import make_route, make_waypoint, make_weather


# ---------------------------------------------------------------------------
# extract_features
# ---------------------------------------------------------------------------


class TestExtractFeatures:
    def test_nine_features_returned(self):
        route = make_route(total_duration_minutes=100)
        features = extract_features(route, min_duration=100)
        assert len(features) == 9

    def test_duration_ratio_is_one_for_fastest(self):
        route = make_route(total_duration_minutes=100)
        features = extract_features(route, min_duration=100)
        assert features[0] == pytest.approx(1.0)

    def test_duration_ratio_greater_for_slower(self):
        route = make_route(total_duration_minutes=200)
        features = extract_features(route, min_duration=100)
        assert features[0] == pytest.approx(2.0)

    def test_no_weather_returns_zeroed_features(self):
        """If waypoints have no weather data, features 1-8 should be 0."""
        wp = make_waypoint(weather=None)
        route = make_route(total_duration_minutes=100, waypoints=[wp])
        features = extract_features(route, min_duration=100)
        assert all(f == 0.0 for f in features[1:])

    def test_adverse_waypoints_fraction(self):
        """weather_code >= 61 counts as adverse."""
        w_clear = make_weather(weather_code=1)
        w_rain = make_weather(weather_code=65)
        wps = [
            make_waypoint(weather=w_clear),
            make_waypoint(weather=w_rain),
        ]
        route = make_route(total_duration_minutes=100, waypoints=wps)
        features = extract_features(route, min_duration=100)
        # pct_adverse = 1/2 = 0.5
        assert features[7] == pytest.approx(0.5)

    def test_wind_and_precip_features(self):
        w1 = make_weather(wind_speed_kmh=20.0, precipitation_mm=2.0, precipitation_probability=40)
        w2 = make_weather(wind_speed_kmh=60.0, precipitation_mm=8.0, precipitation_probability=80)
        wps = [make_waypoint(weather=w1), make_waypoint(weather=w2)]
        route = make_route(total_duration_minutes=100, waypoints=wps)
        features = extract_features(route, min_duration=100)

        # avg_wind = 40, max_wind = 60
        assert features[3] == pytest.approx(40.0)
        assert features[4] == pytest.approx(60.0)
        # avg_precip = 5, max_precip = 8
        assert features[5] == pytest.approx(5.0)
        assert features[6] == pytest.approx(8.0)
        # avg_precip_prob = 60
        assert features[8] == pytest.approx(60.0)

    def test_min_duration_zero_handled(self):
        """min_duration=0 should not cause ZeroDivisionError (uses max(0,1))."""
        route = make_route(total_duration_minutes=100)
        features = extract_features(route, min_duration=0)
        assert features[0] == pytest.approx(100.0)


# ---------------------------------------------------------------------------
# _check_advisory_conditions
# ---------------------------------------------------------------------------


class TestCheckAdvisoryConditions:
    def test_no_weather_returns_empty(self):
        wp = make_waypoint(weather=None)
        assert _check_advisory_conditions(wp) == []

    def test_clear_weather_returns_empty(self):
        wp = make_waypoint(weather=make_weather(weather_code=1, precipitation_mm=0, wind_speed_kmh=10))
        assert _check_advisory_conditions(wp) == []

    def test_heavy_rain_code_65(self):
        wp = make_waypoint(weather=make_weather(weather_code=65))
        results = _check_advisory_conditions(wp)
        types = [(t, s) for t, s, _ in results]
        assert ("heavy_rain", "danger") in types

    def test_heavy_rain_code_82(self):
        wp = make_waypoint(weather=make_weather(weather_code=82))
        results = _check_advisory_conditions(wp)
        types = [(t, s) for t, s, _ in results]
        assert ("heavy_rain", "danger") in types

    def test_heavy_rain_by_precipitation(self):
        wp = make_waypoint(weather=make_weather(weather_code=0, precipitation_mm=8.0))
        results = _check_advisory_conditions(wp)
        types = [(t, s) for t, s, _ in results]
        assert ("heavy_rain", "danger") in types

    def test_moderate_rain_code_63(self):
        wp = make_waypoint(weather=make_weather(weather_code=63))
        results = _check_advisory_conditions(wp)
        types = [(t, s) for t, s, _ in results]
        assert ("moderate_rain", "warning") in types

    def test_moderate_rain_code_81(self):
        wp = make_waypoint(weather=make_weather(weather_code=81))
        results = _check_advisory_conditions(wp)
        types = [(t, s) for t, s, _ in results]
        assert ("moderate_rain", "warning") in types

    def test_moderate_rain_by_precipitation(self):
        wp = make_waypoint(weather=make_weather(weather_code=0, precipitation_mm=5.0))
        results = _check_advisory_conditions(wp)
        types = [(t, s) for t, s, _ in results]
        assert ("moderate_rain", "warning") in types

    def test_freezing_rain(self):
        for code in (56, 57, 66, 67):
            wp = make_waypoint(weather=make_weather(weather_code=code))
            results = _check_advisory_conditions(wp)
            types = [(t, s) for t, s, _ in results]
            assert ("freezing_rain", "danger") in types, f"Failed for code {code}"

    def test_heavy_snow(self):
        for code in (73, 75, 86):
            wp = make_waypoint(weather=make_weather(weather_code=code))
            results = _check_advisory_conditions(wp)
            types = [(t, s) for t, s, _ in results]
            assert ("heavy_snow", "danger") in types, f"Failed for code {code}"

    def test_snow_warning(self):
        for code in (71, 77, 85):
            wp = make_waypoint(weather=make_weather(weather_code=code))
            results = _check_advisory_conditions(wp)
            types = [(t, s) for t, s, _ in results]
            assert ("snow", "warning") in types, f"Failed for code {code}"

    def test_high_wind_danger(self):
        wp = make_waypoint(weather=make_weather(wind_speed_kmh=80.0))
        results = _check_advisory_conditions(wp)
        types = [(t, s) for t, s, _ in results]
        assert ("high_wind", "danger") in types

    def test_high_wind_warning(self):
        wp = make_waypoint(weather=make_weather(wind_speed_kmh=60.0))
        results = _check_advisory_conditions(wp)
        types = [(t, s) for t, s, _ in results]
        assert ("high_wind", "warning") in types

    def test_thunderstorm(self):
        wp = make_waypoint(weather=make_weather(weather_code=95))
        results = _check_advisory_conditions(wp)
        types = [(t, s) for t, s, _ in results]
        assert ("thunderstorm", "danger") in types

    def test_hail(self):
        for code in (96, 99):
            wp = make_waypoint(weather=make_weather(weather_code=code))
            results = _check_advisory_conditions(wp)
            types = [(t, s) for t, s, _ in results]
            assert ("hail", "danger") in types, f"Failed for code {code}"

    def test_fog(self):
        for code in (45, 48):
            wp = make_waypoint(weather=make_weather(weather_code=code))
            results = _check_advisory_conditions(wp)
            types = [(t, s) for t, s, _ in results]
            assert ("fog", "warning") in types, f"Failed for code {code}"


# ---------------------------------------------------------------------------
# _generate_reason
# ---------------------------------------------------------------------------


class TestGenerateReason:
    def test_fastest_route_with_clear_weather(self):
        route = make_route(total_duration_minutes=100)
        reason = _generate_reason(route, duration_score=100, weather_score=85, min_duration=100)
        assert "Fastest route" in reason
        assert "mostly clear" in reason

    def test_slower_route(self):
        route = make_route(total_duration_minutes=120)
        reason = _generate_reason(route, duration_score=80, weather_score=85, min_duration=100)
        assert "20 min longer" in reason

    def test_fair_weather(self):
        route = make_route(total_duration_minutes=100)
        reason = _generate_reason(route, duration_score=100, weather_score=65, min_duration=100)
        assert "fair weather" in reason

    def test_some_adverse_weather(self):
        route = make_route(total_duration_minutes=100)
        reason = _generate_reason(route, duration_score=100, weather_score=50, min_duration=100)
        assert "some adverse" in reason

    def test_poor_weather(self):
        route = make_route(total_duration_minutes=100)
        reason = _generate_reason(route, duration_score=100, weather_score=30, min_duration=100)
        assert "poor weather" in reason


# ---------------------------------------------------------------------------
# score_routes
# ---------------------------------------------------------------------------


class TestScoreRoutes:
    @pytest.mark.asyncio
    async def test_returns_recommendation_with_scores(self):
        """score_routes returns a RouteRecommendation with scores for each route."""
        route1 = make_route(route_index=0, total_duration_minutes=100)
        route2 = make_route(route_index=1, total_duration_minutes=120)

        with patch("app.services.scoring._reverse_geocode_batch", new_callable=AsyncMock) as mock_geo:
            mock_geo.return_value = {}
            result = await score_routes([route1, route2])

        assert result.recommended_route_index in (0, 1)
        assert len(result.scores) == 2
        assert len(result.advisories) == 2

    @pytest.mark.asyncio
    async def test_scores_clipped_to_0_100(self):
        """ML model predictions should be clipped to [0, 100]."""
        route = make_route(route_index=0, total_duration_minutes=100)

        with patch("app.services.scoring._reverse_geocode_batch", new_callable=AsyncMock) as mock_geo:
            mock_geo.return_value = {}
            result = await score_routes([route])

        score = result.scores[0].overall_score
        assert 0 <= score <= 100

    @pytest.mark.asyncio
    async def test_empty_routes_raises(self):
        with pytest.raises(ValueError, match="No routes to score"):
            await score_routes([])

    @pytest.mark.asyncio
    async def test_advisories_generated_for_bad_weather(self):
        """Routes with bad weather should produce advisories."""
        w_storm = make_weather(weather_code=95, wind_speed_kmh=80)
        wp = make_waypoint(weather=w_storm)
        route = make_route(route_index=0, waypoints=[wp])

        with patch("app.services.scoring._reverse_geocode_batch", new_callable=AsyncMock) as mock_geo:
            mock_geo.return_value = {
                (wp.location.lat, wp.location.lng): "TestTown, CA"
            }
            result = await score_routes([route])

        assert len(result.advisories[0]) > 0
        severities = [a.severity for a in result.advisories[0]]
        assert "danger" in severities

    @pytest.mark.asyncio
    async def test_recommendation_reason_contains_text(self):
        route = make_route(route_index=0, total_duration_minutes=100)

        with patch("app.services.scoring._reverse_geocode_batch", new_callable=AsyncMock) as mock_geo:
            mock_geo.return_value = {}
            result = await score_routes([route])

        reason = result.scores[0].recommendation_reason
        assert isinstance(reason, str)
        assert len(reason) > 0

    @pytest.mark.asyncio
    async def test_best_route_is_argmax(self):
        """The recommended route should be the one with the highest score."""
        # Two routes: one fast+clear, one slow+bad weather
        w_clear = make_weather(weather_code=0, wind_speed_kmh=5, precipitation_mm=0)
        w_storm = make_weather(weather_code=95, wind_speed_kmh=90, precipitation_mm=10)
        route_good = make_route(
            route_index=0,
            total_duration_minutes=100,
            waypoints=[make_waypoint(weather=w_clear)],
        )
        route_bad = make_route(
            route_index=1,
            total_duration_minutes=200,
            waypoints=[make_waypoint(weather=w_storm)],
        )

        with patch("app.services.scoring._reverse_geocode_batch", new_callable=AsyncMock) as mock_geo:
            mock_geo.return_value = {}
            result = await score_routes([route_good, route_bad])

        # The good route should score higher
        assert result.scores[0].overall_score >= result.scores[1].overall_score
        assert result.recommended_route_index == 0
