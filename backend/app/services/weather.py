import asyncio
import logging
from datetime import datetime

import httpx

from ..models import Waypoint, WeatherData
from .http_client import request_with_retry

logger = logging.getLogger(__name__)

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"

HOURLY_PARAMS = [
    "temperature_2m",
    "apparent_temperature",
    "precipitation",
    "precipitation_probability",
    "weather_code",
    "wind_speed_10m",
    "relative_humidity_2m",
]

WMO_CODES = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    71: "Slight snow",
    73: "Moderate snow",
    75: "Heavy snow",
    77: "Snow grains",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    85: "Slight snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail",
}


_semaphore = asyncio.Semaphore(5)


async def _fetch_weather_for_point(
    client: httpx.AsyncClient,
    lat: float,
    lng: float,
    target_time: datetime,
) -> WeatherData:
    """Fetch hourly forecast for a single point and extract the closest hour."""
    date_str = target_time.strftime("%Y-%m-%d")
    async with _semaphore:
        response = await request_with_retry(
            client,
            "GET",
            OPEN_METEO_URL,
            params={
                "latitude": round(lat, 4),
                "longitude": round(lng, 4),
                "hourly": ",".join(HOURLY_PARAMS),
                "start_date": date_str,
                "end_date": date_str,
                "timezone": "auto",
            },
        )
    response.raise_for_status()
    data = response.json()

    if "hourly" not in data:
        raise RuntimeError(
            f"Open-Meteo error for ({lat}, {lng}) on {date_str}: {data}"
        )

    hourly = data["hourly"]

    # Use the nearest hour index
    idx = min(target_time.hour, len(hourly["time"]) - 1)

    weather_code = hourly["weather_code"][idx]

    return WeatherData(
        temperature_c=hourly["temperature_2m"][idx],
        apparent_temperature_c=hourly["apparent_temperature"][idx],
        precipitation_mm=hourly["precipitation"][idx],
        precipitation_probability=hourly["precipitation_probability"][idx],
        weather_code=weather_code,
        weather_description=WMO_CODES.get(weather_code, "Unknown"),
        wind_speed_kmh=hourly["wind_speed_10m"][idx],
        humidity_percent=hourly["relative_humidity_2m"][idx],
    )


client = httpx.AsyncClient(timeout=30.0)


async def get_weather_for_waypoints(
    waypoints: list[Waypoint],
) -> list[Waypoint]:
    """Fetch weather for all waypoints in parallel."""
    tasks = [
        _fetch_weather_for_point(
            client,
            wp.location.lat,
            wp.location.lng,
            wp.estimated_time,
        )
        for wp in waypoints
    ]
    weather_results = await asyncio.gather(*tasks, return_exceptions=True)

    for wp, weather in zip(waypoints, weather_results):
        if isinstance(weather, Exception):
            logger.warning(
                "Weather fetch failed for (%s, %s): %s",
                wp.location.lat, wp.location.lng, weather,
            )
            continue  # leave wp.weather as None
        wp.weather = weather

    return waypoints
