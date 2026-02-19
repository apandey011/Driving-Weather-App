export interface LatLng {
  lat: number;
  lng: number;
}

export interface WeatherData {
  temperature_c: number;
  apparent_temperature_c: number;
  precipitation_mm: number;
  precipitation_probability: number;
  weather_code: number;
  weather_description: string;
  wind_speed_kmh: number;
  humidity_percent: number;
}

export interface Waypoint {
  location: LatLng;
  minutes_from_start: number;
  estimated_time: string;
  weather: WeatherData | null;
}

export interface RouteWithWeather {
  route_index: number;
  overview_polyline: string;
  summary: string;
  total_duration_minutes: number;
  total_distance_km: number;
  waypoints: Waypoint[];
}

export type AdvisorySeverity = "warning" | "danger";

export interface WeatherAdvisory {
  type: string;
  severity: AdvisorySeverity;
  message: string;
}

export interface RouteScore {
  overall_score: number;
  duration_score: number;
  weather_score: number;
  recommendation_reason: string;
}

export interface RouteRecommendation {
  recommended_route_index: number;
  scores: RouteScore[];
  advisories: WeatherAdvisory[][];
}

export interface MultiRouteResponse {
  origin_address: string;
  destination_address: string;
  routes: RouteWithWeather[];
  recommendation?: RouteRecommendation;
}
