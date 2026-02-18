import { Waypoint, WeatherAdvisory } from "../types";
import { toF, toMph, weatherEmoji, formatDurationCompact, formatTime } from "../utils";
import WeatherAdvisories from "./WeatherAdvisories";

interface Props {
  waypoints: Waypoint[];
  useFahrenheit: boolean;
  onSelectWaypoint: (idx: number) => void;
  onClose: () => void;
  advisories?: WeatherAdvisory[];
}

export default function WeatherPanel({ waypoints, useFahrenheit, onSelectWaypoint, onClose, advisories }: Props) {
  return (
    <div className="weather-panel" role="region" aria-label="Weather details">
      <div className="panel-header">
        <h3 className="panel-title">Weather Along Route</h3>
        <button className="panel-close" onClick={onClose} aria-label="Close">&times;</button>
      </div>
      {advisories && advisories.length > 0 && (
        <WeatherAdvisories advisories={advisories} />
      )}
      <div className="panel-list">
        {waypoints.map((wp, idx) => {
          const { weather } = wp;
          const temp = useFahrenheit
            ? toF(weather.temperature_c)
            : Math.round(weather.temperature_c);
          const unit = useFahrenheit ? "\u00B0F" : "\u00B0C";
          const wind = useFahrenheit
            ? `${toMph(weather.wind_speed_kmh)} mph`
            : `${Math.round(weather.wind_speed_kmh)} km/h`;

          const isFirst = idx === 0;
          const isLast = idx === waypoints.length - 1;

          return (
            <div
              key={idx}
              className={`panel-row ${isFirst || isLast ? "panel-row-endpoint" : ""}`}
              onClick={() => onSelectWaypoint(idx)}
            >
              <span className="panel-emoji">
                {weatherEmoji(weather.weather_code)}
              </span>
              <div className="panel-info">
                <span className="panel-time">
                  {isFirst
                    ? "Start"
                    : isLast
                      ? "Arrive"
                      : formatDurationCompact(wp.minutes_from_start)}
                </span>
                <span className="panel-clock">{formatTime(wp.estimated_time)}</span>
              </div>
              <span className="panel-temp">
                {temp}{unit}
              </span>
              <span className="panel-wind">{wind}</span>
              <span className="panel-precip">
                {weather.precipitation_probability}%
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
