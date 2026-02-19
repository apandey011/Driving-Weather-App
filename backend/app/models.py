from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import AwareDatetime, BaseModel, Field


class RouteRequest(BaseModel):
    origin: str = Field(min_length=1, max_length=500)
    destination: str = Field(min_length=1, max_length=500)
    departure_time: AwareDatetime | None = None


class LatLng(BaseModel):
    lat: float
    lng: float


class WeatherData(BaseModel):
    temperature_c: float
    apparent_temperature_c: float
    precipitation_mm: float
    precipitation_probability: int
    weather_code: int
    weather_description: str
    wind_speed_kmh: float
    humidity_percent: int


class Waypoint(BaseModel):
    location: LatLng
    minutes_from_start: int
    estimated_time: datetime
    weather: WeatherData | None = None


class RouteWithWeather(BaseModel):
    route_index: int
    overview_polyline: str
    summary: str
    total_duration_minutes: int
    total_distance_km: float
    waypoints: list[Waypoint]


class WeatherAdvisory(BaseModel):
    type: str
    severity: Literal["warning", "danger"]
    message: str


class RouteScore(BaseModel):
    overall_score: float
    duration_score: float
    weather_score: float
    recommendation_reason: str


class RouteRecommendation(BaseModel):
    recommended_route_index: int
    scores: list[RouteScore]
    advisories: list[list[WeatherAdvisory]]


class MultiRouteResponse(BaseModel):
    origin_address: str
    destination_address: str
    routes: list[RouteWithWeather]
    recommendation: RouteRecommendation | None = None
