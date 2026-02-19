import logging
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, HTTPException, Request

from .config import settings
from .models import RouteRequest, RouteWithWeather, MultiRouteResponse
from .rate_limit import limiter
from .services.cache import route_cache
from .services.directions import get_routes
from .services.sampling import sample_route_points
from .services.scoring import score_routes
from .services.weather import get_weather_for_waypoints

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/api/route-weather", response_model=MultiRouteResponse)
@limiter.limit(settings.route_weather_rate_limit)
async def route_weather(request: Request, payload: RouteRequest):
    departure_iso = payload.departure_time.isoformat() if payload.departure_time else None
    cache_key = route_cache.make_key(payload.origin, payload.destination, departure_iso)
    cached = route_cache.get(cache_key)
    if cached:
        return cached

    try:
        routes_data = await get_routes(payload.origin, payload.destination)
        departure = payload.departure_time or datetime.now(timezone.utc)

        # Sample waypoints for each route
        all_route_waypoints = []
        for route in routes_data["routes"]:
            waypoints = sample_route_points(route["steps"], departure)
            all_route_waypoints.append(waypoints)

        # Deduplicate weather calls across routes.
        # Routes often overlap, so many waypoints share nearly identical
        # locations and times. Key by (lat rounded to 2dp, lng rounded to
        # 2dp, hour) — ~1.1 km resolution, same hour.
        unique_weather = {}  # key → waypoint (representative)
        for waypoints in all_route_waypoints:
            for wp in waypoints:
                key = (
                    round(wp.location.lat, 2),
                    round(wp.location.lng, 2),
                    wp.estimated_time.replace(minute=0, second=0, microsecond=0),
                )
                if key not in unique_weather:
                    unique_weather[key] = wp

        # Fetch weather for unique waypoints only
        unique_list = list(unique_weather.values())
        await get_weather_for_waypoints(unique_list)

        # Build lookup and assign weather to all waypoints
        weather_lookup = {k: wp.weather for k, wp in unique_weather.items()}
        for waypoints in all_route_waypoints:
            for wp in waypoints:
                key = (
                    round(wp.location.lat, 2),
                    round(wp.location.lng, 2),
                    wp.estimated_time.replace(minute=0, second=0, microsecond=0),
                )
                wp.weather = weather_lookup[key]

        # Build response
        route_results = []
        for idx, (route, waypoints) in enumerate(
            zip(routes_data["routes"], all_route_waypoints)
        ):
            route_results.append(
                RouteWithWeather(
                    route_index=idx,
                    overview_polyline=route["overview_polyline"],
                    summary=route["summary"],
                    total_duration_minutes=route["total_duration_seconds"] // 60,
                    total_distance_km=round(
                        route["total_distance_meters"] / 1000, 1
                    ),
                    waypoints=waypoints,
                )
            )

        recommendation = await score_routes(route_results)

        response = MultiRouteResponse(
            origin_address=routes_data["origin_address"],
            destination_address=routes_data["destination_address"],
            routes=route_results,
            recommendation=recommendation,
        )
        route_cache.set(cache_key, response)
        return response
    except HTTPException:
        raise
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="External API timed out")
    except httpx.HTTPStatusError as exc:
        logger.error("Upstream API error: %s", exc.response.status_code)
        raise HTTPException(
            status_code=502,
            detail=f"Upstream API error: {exc.response.status_code}",
        )
    except Exception:
        logger.exception("Unexpected error in route_weather")
        raise HTTPException(status_code=500, detail="Internal server error")
