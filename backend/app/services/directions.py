import logging

import httpx
from fastapi import HTTPException

from ..config import settings

logger = logging.getLogger(__name__)

DIRECTIONS_URL = "https://maps.googleapis.com/maps/api/directions/json"

client = httpx.AsyncClient(timeout=30.0)


async def get_routes(origin: str, destination: str) -> dict:
    """Fetch all route alternatives from Google Directions API."""
    logger.info("Fetching directions: %s -> %s", origin, destination)
    response = await client.get(
        DIRECTIONS_URL,
        params={
            "origin": origin,
            "destination": destination,
            "mode": "driving",
            "alternatives": "true",
            "key": settings.google_maps_api_key,
        },
    )
    response.raise_for_status()
    data = response.json()

    if data["status"] != "OK":
        raise HTTPException(
            status_code=400,
            detail=f"Directions API error: {data['status']}",
        )

    if not data["routes"]:
        raise HTTPException(status_code=404, detail="No routes found")

    first_leg = data["routes"][0]["legs"][0]
    last_leg = data["routes"][0]["legs"][-1]

    routes = []
    for route in data["routes"]:
        steps = []
        for leg in route["legs"]:
            for step in leg["steps"]:
                steps.append(
                    {
                        "duration_seconds": step["duration"]["value"],
                        "distance_meters": step["distance"]["value"],
                        "start_location": step["start_location"],
                        "end_location": step["end_location"],
                        "polyline": step["polyline"]["points"],
                    }
                )

        routes.append(
            {
                "overview_polyline": route["overview_polyline"]["points"],
                "summary": route.get("summary", ""),
                "total_duration_seconds": sum(s["duration_seconds"] for s in steps),
                "total_distance_meters": sum(s["distance_meters"] for s in steps),
                "steps": steps,
            }
        )

    return {
        "origin_address": first_leg["start_address"],
        "destination_address": last_leg["end_address"],
        "routes": routes,
    }
