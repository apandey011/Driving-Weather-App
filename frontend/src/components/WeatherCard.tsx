import { Waypoint } from "../types";
import { toF, toMph, weatherEmoji, formatTime } from "../utils";

interface Props {
  waypoint: Waypoint;
  useFahrenheit: boolean;
}

export default function WeatherCard({ waypoint, useFahrenheit }: Props) {
  const { weather, minutes_from_start, estimated_time } = waypoint;

  if (!weather) return null;

  const temp = useFahrenheit ? toF(weather.temperature_c) : Math.round(weather.temperature_c);
  const feelsLike = useFahrenheit ? toF(weather.apparent_temperature_c) : Math.round(weather.apparent_temperature_c);
  const unit = useFahrenheit ? "\u00B0F" : "\u00B0C";
  const wind = useFahrenheit
    ? `${toMph(weather.wind_speed_kmh)} mph`
    : `${Math.round(weather.wind_speed_kmh)} km/h`;

  return (
    <div className="weather-card">
      <div className="weather-card-header">
        <span className="weather-emoji">{weatherEmoji(weather.weather_code)}</span>
        <span className="weather-time">
          +{minutes_from_start} min ({formatTime(estimated_time)})
        </span>
      </div>
      <div className="weather-temp">{temp}{unit}</div>
      <div className="weather-desc">{weather.weather_description}</div>
      <div className="weather-details">
        <span>Feels like {feelsLike}{unit}</span>
        <span>Precip: {weather.precipitation_probability}%</span>
        <span>Wind: {wind}</span>
        <span>Humidity: {weather.humidity_percent}%</span>
      </div>
    </div>
  );
}
