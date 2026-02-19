import { memo, useEffect } from "react";
import {
  AdvancedMarker,
  InfoWindow,
  useAdvancedMarkerRef,
  useMap,
} from "@vis.gl/react-google-maps";
import { Waypoint } from "../types";
import { toF, weatherEmoji } from "../utils";
import WeatherCard from "./WeatherCard";

interface Props {
  waypoint: Waypoint;
  useFahrenheit: boolean;
  isSelected: boolean;
  onSelect: () => void;
  onDeselect: () => void;
  scale: number;
  dimmed?: boolean;
}

export default memo(function WeatherMarker({ waypoint, useFahrenheit, isSelected, onSelect, onDeselect, scale, dimmed }: Props) {
  const [markerRef, marker] = useAdvancedMarkerRef();
  const map = useMap();

  const { weather, location } = waypoint;

  useEffect(() => {
    if (isSelected && map) {
      map.panTo({ lat: location.lat, lng: location.lng });
    }
  }, [isSelected, map, location.lat, location.lng]);

  if (!weather) return null;

  return (
    <>
      <AdvancedMarker
        ref={markerRef}
        position={{ lat: location.lat, lng: location.lng }}
        onClick={onSelect}
      >
        <div className={`marker-content${dimmed ? " marker-content-dimmed" : ""}`} style={{ transform: `scale(${scale})` }}>
          <span>{weatherEmoji(weather.weather_code)}</span>
          <span>{useFahrenheit ? toF(weather.temperature_c) : Math.round(weather.temperature_c)}&deg;</span>
        </div>
      </AdvancedMarker>

      {isSelected && (
        <InfoWindow anchor={marker} onCloseClick={onDeselect}>
          <WeatherCard waypoint={waypoint} useFahrenheit={useFahrenheit} />
        </InfoWindow>
      )}
    </>
  );
});
