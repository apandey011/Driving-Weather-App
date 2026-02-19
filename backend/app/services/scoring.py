"""Route scoring service using a trained ML model and rule-based advisories."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import httpx
import joblib
import numpy as np

from ..config import settings
from ..models import (
    RouteRecommendation,
    RouteScore,
    RouteWithWeather,
    Waypoint,
    WeatherAdvisory,
    WeatherData,
)

logger = logging.getLogger(__name__)

GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"

geocode_client = httpx.AsyncClient(timeout=10.0)

# ---------------------------------------------------------------------------
# WMO code → severity (0.0 = benign, 1.0 = extreme)
# ---------------------------------------------------------------------------
WMO_SEVERITY: dict[int, float] = {
    0: 0.0,
    1: 0.02,
    2: 0.05,
    3: 0.08,
    45: 0.15,
    48: 0.20,
    51: 0.10,
    53: 0.20,
    55: 0.30,
    56: 0.40,
    57: 0.55,
    61: 0.20,
    63: 0.40,
    65: 0.70,
    66: 0.60,
    67: 0.80,
    71: 0.35,
    73: 0.55,
    75: 0.80,
    77: 0.40,
    80: 0.25,
    81: 0.45,
    82: 0.75,
    85: 0.40,
    86: 0.75,
    95: 0.85,
    96: 0.95,
    99: 1.0,
}

# ---------------------------------------------------------------------------
# Load the pre-trained model once at import time
# ---------------------------------------------------------------------------
_MODEL_PATH = Path(__file__).resolve().parent.parent / "ml" / "route_model.joblib"
try:
    _model = joblib.load(_MODEL_PATH)
except FileNotFoundError:
    raise RuntimeError(
        f"ML model not found at {_MODEL_PATH}. Run: python -m app.ml.train_model"
    )


# ---------------------------------------------------------------------------
# Feature extraction
# ---------------------------------------------------------------------------

def _weather_list(waypoints: list[Waypoint]) -> list[WeatherData]:
    return [wp.weather for wp in waypoints if wp.weather is not None]


def extract_features(route: RouteWithWeather, min_duration: int) -> list[float]:
    """Extract the 9-element feature vector expected by the ML model."""
    weathers = _weather_list(route.waypoints)

    if not weathers:
        # No weather data — assume neutral conditions
        return [
            route.total_duration_minutes / max(min_duration, 1),
            0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
        ]

    severities = [WMO_SEVERITY.get(w.weather_code, 0.5) for w in weathers]
    wind_speeds = [w.wind_speed_kmh for w in weathers]
    precips = [w.precipitation_mm for w in weathers]
    precip_probs = [w.precipitation_probability for w in weathers]
    adverse_count = sum(1 for w in weathers if w.weather_code >= 61)

    return [
        route.total_duration_minutes / max(min_duration, 1),   # duration_ratio
        sum(severities) / len(severities),                      # avg_weather_severity
        max(severities),                                        # max_weather_severity
        sum(wind_speeds) / len(wind_speeds),                    # avg_wind_speed
        max(wind_speeds),                                       # max_wind_speed
        sum(precips) / len(precips),                            # avg_precipitation
        max(precips),                                           # max_precipitation
        adverse_count / len(weathers),                          # pct_adverse_waypoints
        sum(precip_probs) / len(precip_probs),                  # avg_precip_probability
    ]


# ---------------------------------------------------------------------------
# Reverse geocoding
# ---------------------------------------------------------------------------

def _format_coords(lat: float, lng: float) -> str:
    """Format coordinates as a human-readable string, e.g. '35.1°N, 117.2°W'."""
    ns = "N" if lat >= 0 else "S"
    ew = "E" if lng >= 0 else "W"
    return f"{abs(lat):.1f}\u00b0{ns}, {abs(lng):.1f}\u00b0{ew}"


async def _reverse_geocode_batch(
    coords: list[tuple[float, float]],
) -> dict[tuple[float, float], str]:
    """Reverse-geocode a list of (lat, lng) pairs to 'Town, State' strings.

    Deduplicates by rounding to 2 decimal places (~1.1 km).
    Falls back to formatted coordinates when geocoding fails.
    """
    # Deduplicate by rounded coords
    unique: dict[tuple[float, float], tuple[float, float]] = {}
    for lat, lng in coords:
        key = (round(lat, 2), round(lng, 2))
        if key not in unique:
            unique[key] = (lat, lng)

    results: dict[tuple[float, float], str] = {}

    tasks = []
    keys = []
    for key, (lat, lng) in unique.items():
        keys.append(key)
        tasks.append(
            geocode_client.get(
                GEOCODE_URL,
                params={
                    "latlng": f"{lat},{lng}",
                    "key": settings.google_maps_api_key,
                },
            )
        )
    responses = await asyncio.gather(*tasks, return_exceptions=True)

    for key, resp in zip(keys, responses):
        lat, lng = unique[key]
        fallback = _format_coords(lat, lng)

        if isinstance(resp, Exception):
            results[key] = fallback
            continue
        data = resp.json()
        if data.get("status") == "OK" and data.get("results"):
            components = data["results"][0].get("address_components", [])
            town = ""
            county = ""
            feature = ""
            state = ""
            for comp in components:
                types = comp.get("types", [])
                if "locality" in types:
                    town = comp["long_name"]
                elif "administrative_area_level_3" in types and not town:
                    town = comp["long_name"]
                elif "administrative_area_level_2" in types:
                    county = comp["long_name"]
                elif "natural_feature" in types:
                    feature = comp["long_name"]
                elif "administrative_area_level_1" in types:
                    state = comp.get("short_name", comp["long_name"])
            name = town or county or feature
            if name and state:
                results[key] = f"{name}, {state}"
            elif name:
                results[key] = name
            elif state:
                results[key] = state
            else:
                results[key] = data["results"][0].get(
                    "formatted_address", fallback
                )
        else:
            results[key] = fallback

    # Map original coords to results via their rounded key
    full_results: dict[tuple[float, float], str] = {}
    for lat, lng in coords:
        key = (round(lat, 2), round(lng, 2))
        full_results[(lat, lng)] = results.get(key, _format_coords(lat, lng))

    return full_results


# ---------------------------------------------------------------------------
# Advisory generation (rule-based)
# ---------------------------------------------------------------------------

def _check_advisory_conditions(
    wp: Waypoint,
) -> list[tuple[str, str, str]]:
    """Return list of (type, severity, message_template) for a single waypoint."""
    w = wp.weather
    if w is None:
        return []

    triggered: list[tuple[str, str, str]] = []

    checks: list[tuple[str, str, bool, str]] = [
        (
            "heavy_rain", "danger",
            w.weather_code in (65, 82) or w.precipitation_mm >= 7.5,
            "Heavy rain expected near {loc}",
        ),
        (
            "moderate_rain", "warning",
            w.weather_code in (63, 81) or (4.0 <= w.precipitation_mm < 7.5),
            "Moderate rain expected near {loc}",
        ),
        (
            "freezing_rain", "danger",
            w.weather_code in (56, 57, 66, 67),
            "Freezing rain/drizzle near {loc} \u2014 road ice likely",
        ),
        (
            "heavy_snow", "danger",
            w.weather_code in (73, 75, 86),
            "Heavy snow expected near {loc}",
        ),
        (
            "snow", "warning",
            w.weather_code in (71, 77, 85),
            "Snow expected near {loc}",
        ),
        (
            "high_wind", "danger",
            w.wind_speed_kmh >= 75,
            f"Dangerous winds ({round(w.wind_speed_kmh)} km/h) near {{loc}}",
        ),
        (
            "high_wind", "warning",
            50 <= w.wind_speed_kmh < 75,
            f"Strong winds ({round(w.wind_speed_kmh)} km/h) near {{loc}}",
        ),
        (
            "thunderstorm", "danger",
            w.weather_code == 95,
            "Thunderstorm expected near {loc}",
        ),
        (
            "hail", "danger",
            w.weather_code in (96, 99),
            "Thunderstorm with hail near {loc}",
        ),
        (
            "fog", "warning",
            w.weather_code in (45, 48),
            "Fog near {loc} \u2014 reduced visibility",
        ),
    ]

    for adv_type, severity, condition, template in checks:
        if condition:
            triggered.append((adv_type, severity, template))

    return triggered


async def _collect_advisories(waypoints: list[Waypoint]) -> list[WeatherAdvisory]:
    """Generate weather advisories with location names for a route's waypoints."""
    # First pass: find which waypoints trigger advisories (dedup by type+severity)
    seen: set[tuple[str, str]] = set()
    pending: list[tuple[str, str, str, float, float]] = []  # type, severity, template, lat, lng

    for wp in waypoints:
        triggered = _check_advisory_conditions(wp)
        for adv_type, severity, template in triggered:
            if (adv_type, severity) not in seen:
                seen.add((adv_type, severity))
                pending.append((
                    adv_type, severity, template,
                    wp.location.lat, wp.location.lng,
                ))

    if not pending:
        return []

    # Batch reverse-geocode all advisory locations
    coords = [(lat, lng) for _, _, _, lat, lng in pending]
    location_names = await _reverse_geocode_batch(coords)

    # Build advisories with resolved location names
    advisories: list[WeatherAdvisory] = []
    for adv_type, severity, template, lat, lng in pending:
        loc_name = location_names.get((lat, lng), "unknown location")
        message = template.format(loc=loc_name)
        advisories.append(
            WeatherAdvisory(type=adv_type, severity=severity, message=message)
        )

    advisories.sort(key=lambda a: (0 if a.severity == "danger" else 1, a.type))
    return advisories


# ---------------------------------------------------------------------------
# Reason text
# ---------------------------------------------------------------------------

def _generate_reason(
    route: RouteWithWeather,
    duration_score: float,
    weather_score: float,
    min_duration: int,
) -> str:
    parts: list[str] = []

    if route.total_duration_minutes <= min_duration:
        parts.append("Fastest route")
    else:
        extra = route.total_duration_minutes - min_duration
        parts.append(f"{extra} min longer than fastest")

    if weather_score >= 80:
        parts.append("mostly clear weather")
    elif weather_score >= 60:
        parts.append("fair weather conditions")
    elif weather_score >= 40:
        parts.append("some adverse weather")
    else:
        parts.append("poor weather conditions")

    return " with ".join(parts) if len(parts) == 2 else parts[0]


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

async def score_routes(routes: list[RouteWithWeather]) -> RouteRecommendation:
    """Score all routes with the ML model and generate advisories."""
    if not routes:
        raise ValueError("No routes to score")

    min_duration = min(r.total_duration_minutes for r in routes)

    # Extract features and predict
    feature_matrix = np.array(
        [extract_features(r, min_duration) for r in routes]
    )
    predicted_scores = _model.predict(feature_matrix)
    predicted_scores = np.clip(predicted_scores, 0, 100)

    # Collect advisories for all routes in parallel (includes reverse geocoding)
    advisory_tasks = [_collect_advisories(r.waypoints) for r in routes]
    all_advisories_raw = await asyncio.gather(*advisory_tasks, return_exceptions=True)
    all_advisories = []
    for a in all_advisories_raw:
        if isinstance(a, list):
            all_advisories.append(a)
        else:
            logger.warning("Advisory collection failed: %s", a)
            all_advisories.append([])

    # Compute sub-scores for the UI
    scores: list[RouteScore] = []

    for idx, route in enumerate(routes):
        overall = round(float(predicted_scores[idx]), 1)

        features = feature_matrix[idx]
        d_score = round(float(1.0 / max(features[0], 0.01) * 100), 1)
        w_score = round(float((1.0 - features[1]) * 100), 1)

        reason = _generate_reason(route, d_score, w_score, min_duration)

        scores.append(
            RouteScore(
                overall_score=overall,
                duration_score=min(d_score, 100),
                weather_score=min(w_score, 100),
                recommendation_reason=reason,
            )
        )

    best_idx = int(np.argmax(predicted_scores))

    return RouteRecommendation(
        recommended_route_index=routes[best_idx].route_index,
        scores=scores,
        advisories=list(all_advisories),
    )
