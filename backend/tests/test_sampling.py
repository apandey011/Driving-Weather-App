"""Tests for app.services.sampling — Haversine, interpolation, route sampling."""

from datetime import datetime, timedelta, timezone

import polyline as polyline_codec

from app.services.sampling import _haversine, _interpolate, sample_route_points


# ---------------------------------------------------------------------------
# Helper: build a step dict from known points
# ---------------------------------------------------------------------------


def _make_step(
    points: list[tuple[float, float]],
    duration_seconds: int,
    distance_meters: float | None = None,
) -> dict:
    """Create a step dict compatible with sample_route_points.

    If *distance_meters* is None, it is computed as the sum of haversine
    distances between consecutive points so that the internal speed
    calculation is consistent.
    """
    if distance_meters is None:
        distance_meters = sum(
            _haversine(points[i], points[i + 1])
            for i in range(len(points) - 1)
        )
    encoded = polyline_codec.encode(points)
    return {
        "duration_seconds": duration_seconds,
        "distance_meters": distance_meters,
        "start_location": {"lat": points[0][0], "lng": points[0][1]},
        "end_location": {"lat": points[-1][0], "lng": points[-1][1]},
        "polyline": encoded,
    }


DEPARTURE = datetime(2026, 2, 16, 10, 0, tzinfo=timezone.utc)

# Well-known coordinates
SF = (37.7749, -122.4194)
LA = (34.0522, -118.2437)

# Nearby points for short-step tests (~1 km apart)
P0 = (37.7749, -122.4194)
P1 = (37.7839, -122.4094)  # ~1.3 km from P0
P2 = (37.7929, -122.3994)  # ~1.3 km from P1
P3 = (37.8019, -122.3894)  # ~1.3 km from P2


# ---------------------------------------------------------------------------
# _haversine
# ---------------------------------------------------------------------------


class TestHaversine:
    def test_same_point_is_zero(self):
        assert _haversine(SF, SF) == 0.0

    def test_sf_to_la_approx_559km(self):
        dist = _haversine(SF, LA)
        # Expected ~559 km
        assert 555_000 < dist < 565_000

    def test_symmetry(self):
        assert abs(_haversine(SF, LA) - _haversine(LA, SF)) < 0.01


# ---------------------------------------------------------------------------
# _interpolate
# ---------------------------------------------------------------------------


class TestInterpolate:
    def test_fraction_zero_returns_p1(self):
        result = _interpolate(SF, LA, 0.0)
        assert result == SF

    def test_fraction_one_returns_p2(self):
        result = _interpolate(SF, LA, 1.0)
        assert result == LA

    def test_fraction_half_returns_midpoint(self):
        result = _interpolate((0.0, 0.0), (10.0, 20.0), 0.5)
        assert abs(result[0] - 5.0) < 1e-9
        assert abs(result[1] - 10.0) < 1e-9


# ---------------------------------------------------------------------------
# sample_route_points
# ---------------------------------------------------------------------------


class TestSampleRoutePoints:
    def test_empty_steps_returns_empty(self):
        assert sample_route_points([], DEPARTURE) == []

    def test_single_short_step_returns_start_and_end(self):
        """A step shorter than 15 min should yield start + end waypoints."""
        # Use nearby points so haversine distance is consistent
        pts = [P0, P1]
        # 10 minutes = 600 seconds, distance = haversine(P0, P1)
        step = _make_step(pts, duration_seconds=600)
        result = sample_route_points([step], DEPARTURE)

        assert len(result) == 2
        # Start
        assert result[0].minutes_from_start == 0
        assert result[0].location.lat == P0[0]
        # End
        assert result[-1].location.lat == P1[0]
        assert result[-1].minutes_from_start == 10  # 600s // 60

    def test_step_exactly_15_min(self):
        """A step lasting exactly 15 min: start + 15-min boundary (equals end)."""
        pts = [P0, P1]
        step = _make_step(pts, duration_seconds=900)  # exactly 15 min
        result = sample_route_points([step], DEPARTURE)

        # start (0 min) + 15-min interpolated point at the end of the segment
        # The end point would have the same minutes_from_start (15), so not duplicated.
        assert len(result) == 2
        assert result[0].minutes_from_start == 0
        assert result[1].minutes_from_start == 15

    def test_45_min_step_produces_multiple_waypoints(self):
        """A 45-min step should yield start + waypoints at 15, 30, 45."""
        pts = [P0, P1, P2, P3]
        step = _make_step(pts, duration_seconds=2700)  # 45 min
        result = sample_route_points([step], DEPARTURE)

        minutes = [wp.minutes_from_start for wp in result]
        assert minutes[0] == 0
        assert 15 in minutes
        assert 30 in minutes
        assert 45 in minutes

    def test_multi_step_boundary_crossing(self):
        """Two consecutive 10-min steps: boundary at 15 min crosses into second step."""
        pts1 = [P0, P1]
        pts2 = [P1, P2]
        step1 = _make_step(pts1, duration_seconds=600)  # 10 min
        step2 = _make_step(pts2, duration_seconds=600)  # 10 min
        result = sample_route_points([step1, step2], DEPARTURE)

        minutes = [wp.minutes_from_start for wp in result]
        assert 0 in minutes
        assert 15 in minutes  # boundary crossed into step2
        assert 20 in minutes  # end point (1200s // 60)

    def test_zero_duration_step_skipped(self):
        """A step with 0 duration/distance should be skipped without error."""
        pts_zero = [P0, P0]
        pts_real = [P0, P1]
        step_zero = _make_step(pts_zero, duration_seconds=0, distance_meters=0)
        step_real = _make_step(pts_real, duration_seconds=600)
        result = sample_route_points([step_zero, step_real], DEPARTURE)

        # Should still have start and end
        assert len(result) >= 2
        assert result[0].minutes_from_start == 0

    def test_end_waypoint_always_included(self):
        """The last waypoint should always match the end location of the last step."""
        pts = [P0, P1]
        step = _make_step(pts, duration_seconds=1200)  # 20 min
        result = sample_route_points([step], DEPARTURE)

        last = result[-1]
        assert abs(last.location.lat - P1[0]) < 0.001
        assert abs(last.location.lng - P1[1]) < 0.001

    def test_estimated_time_offsets_correct(self):
        """estimated_time should equal departure + timedelta(seconds=elapsed)."""
        pts = [P0, P1, P2]
        step = _make_step(pts, duration_seconds=1800)  # 30 min
        result = sample_route_points([step], DEPARTURE)

        assert result[0].estimated_time == DEPARTURE
        # The 15-min waypoint
        wp_15 = [wp for wp in result if wp.minutes_from_start == 15]
        assert len(wp_15) == 1
        assert wp_15[0].estimated_time == DEPARTURE + timedelta(seconds=900)
