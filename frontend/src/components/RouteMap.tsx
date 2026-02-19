import { useEffect, useMemo, useRef, useState } from "react";
import { AdvancedMarker, Map, useMap } from "@vis.gl/react-google-maps";
import { decode } from "@googlemaps/polyline-codec";
import { MultiRouteResponse, Waypoint } from "../types";
import { formatDuration } from "../utils";
import WeatherMarker from "./WeatherMarker";

const MIN_MARKER_DISTANCE_PX = 40;

interface TaggedWaypoint {
  waypoint: Waypoint;
  routeIndex: number;
  wpIndex: number;
}

/**
 * Greedy cross-route filter: keep waypoints whose screen-pixel positions are
 * far enough apart. Operates on waypoints from ALL routes at once so that
 * markers from different routes that overlap are also deduplicated.
 *
 * Returns a Set of "routeIndex-wpIndex" keys for fast lookup during render.
 */
function getVisibleWaypointKeys(
  entries: TaggedWaypoint[],
  map: google.maps.Map,
  selectedRouteIndex: number | null,
  selectedWaypointIdx: number | null,
  threshold: number = MIN_MARKER_DISTANCE_PX,
): Set<string> {
  const projection = map.getProjection();
  if (!projection) return new Set(entries.map((e) => `${e.routeIndex}-${e.wpIndex}`));

  const zoom = map.getZoom() ?? 4;
  const scale = 1 << zoom;

  const pixelCoords = entries.map((e) => {
    const worldPoint = projection.fromLatLngToPoint(
      new google.maps.LatLng(e.waypoint.location.lat, e.waypoint.location.lng),
    )!;
    return { x: worldPoint.x * scale, y: worldPoint.y * scale };
  });

  const keptPx: { x: number; y: number }[] = [];
  const keptKeys = new Set<string>();

  for (let i = 0; i < entries.length; i++) {
    const px = pixelCoords[i];
    const entry = entries[i];
    const isSelected =
      entry.routeIndex === selectedRouteIndex && entry.wpIndex === selectedWaypointIdx;

    let tooClose = false;
    for (const k of keptPx) {
      const dx = px.x - k.x;
      const dy = px.y - k.y;
      if (Math.sqrt(dx * dx + dy * dy) < threshold) {
        tooClose = true;
        break;
      }
    }

    if (!tooClose || isSelected) {
      keptPx.push(px);
      keptKeys.add(`${entry.routeIndex}-${entry.wpIndex}`);
    }
  }

  return keptKeys;
}


interface Props {
  routeData: MultiRouteResponse | null;
  selectedRouteIndex: number | null;
  recommendedRouteIndex: number | null;
  onRouteSelect: (index: number) => void;
  useFahrenheit: boolean;
  selectedWaypointIdx: number | null;
  onSelectWaypoint: (idx: number) => void;
  onDeselectWaypoint: () => void;
}

function RoutesOverlay({
  routeData,
  selectedRouteIndex,
  recommendedRouteIndex,
  onRouteSelect,
  useFahrenheit,
  selectedWaypointIdx,
  onSelectWaypoint,
  onDeselectWaypoint,
}: {
  routeData: MultiRouteResponse;
  selectedRouteIndex: number | null;
  recommendedRouteIndex: number | null;
  onRouteSelect: (index: number) => void;
  useFahrenheit: boolean;
  selectedWaypointIdx: number | null;
  onSelectWaypoint: (idx: number) => void;
  onDeselectWaypoint: () => void;
}) {
  const map = useMap();
  const polylinesRef = useRef<google.maps.Polyline[]>([]);
  const [zoom, setZoom] = useState(4);

  useEffect(() => {
    if (!map) return;
    const listener = map.addListener("zoom_changed", () => {
      setZoom(map.getZoom() ?? 4);
    });
    return () => listener.remove();
  }, [map]);

  // Smooth scaling: markers stay readable at all zoom levels without becoming huge.
  // Uses a sigmoid-like curve that flattens at both ends.
  const SCALE_MIN = 0.8;
  const SCALE_MAX = 1.45;
  const ZOOM_MID = 10;   // zoom level where scale is halfway
  const STEEPNESS = 0.4;
  const t = 1 / (1 + Math.exp(-STEEPNESS * (zoom - ZOOM_MID)));
  const markerScale = SCALE_MIN + (SCALE_MAX - SCALE_MIN) * t;

  // Render polylines for all routes
  useEffect(() => {
    if (!map) return;

    // Clear old polylines
    polylinesRef.current.forEach((p) => p.setMap(null));
    polylinesRef.current = [];

    const bounds = new google.maps.LatLngBounds();

    // Draw unselected routes first (lower z-index), then selected on top
    const sortedRoutes = [...routeData.routes].sort((a, b) => {
      const aSelected = a.route_index === selectedRouteIndex;
      const bSelected = b.route_index === selectedRouteIndex;
      if (aSelected) return 1; // draw selected last (on top)
      if (bSelected) return -1;
      return 0;
    });

    sortedRoutes.forEach((route) => {
      const path = decode(route.overview_polyline).map(([lat, lng]) => ({ lat, lng }));
      const isSelected = route.route_index === selectedRouteIndex;
      const defaultHighlight = recommendedRouteIndex ?? 0;
      const isHighlighted = selectedRouteIndex === null
        ? route.route_index === defaultHighlight
        : isSelected;

      const polyline = new google.maps.Polyline({
        path,
        strokeColor: isHighlighted ? "#4285F4" : "#90B8F8",
        strokeOpacity: isHighlighted ? 0.9 : 0.75,
        strokeWeight: isHighlighted ? 6 : 4,
        zIndex: isHighlighted ? 2 : 1,
        map,
        clickable: true,
      });

      polyline.addListener("click", () => onRouteSelect(route.route_index));

      polyline.addListener("mouseover", () => {
        if (!isHighlighted) {
          polyline.setOptions({ strokeColor: "#7CACF8", strokeOpacity: 0.8, strokeWeight: 5 });
        }
      });
      polyline.addListener("mouseout", () => {
        if (!isHighlighted) {
          polyline.setOptions({ strokeColor: "#90B8F8", strokeOpacity: 0.75, strokeWeight: 4 });
        }
      });

      path.forEach((p) => bounds.extend(p));
      polylinesRef.current.push(polyline);
    });

    map.fitBounds(bounds, 50);

    return () => {
      polylinesRef.current.forEach((p) => p.setMap(null));
    };
  }, [map, routeData, selectedRouteIndex, onRouteSelect]);

  // Compute label positions where each route diverges most from the others
  const routeLabelPositions = useMemo(() => {
    const decodedPaths = routeData.routes.map((route) =>
      decode(route.overview_polyline).map(([lat, lng]) => ({ lat, lng })),
    );

    return routeData.routes.map((route, idx) => {
      const path = decodedPaths[idx];
      const otherPaths = decodedPaths.filter((_, i) => i !== idx);

      // Single route — fall back to midpoint
      if (otherPaths.length === 0) {
        return { routeIndex: route.route_index, position: path[Math.floor(path.length / 2)], duration: route.total_duration_minutes };
      }

      // For each point on this route, find the min distance to any other route
      let bestPoint = path[Math.floor(path.length / 2)];
      let bestMinDist = 0;

      // Sample every few points for performance on long polylines
      const step = Math.max(1, Math.floor(path.length / 100));
      for (let i = 0; i < path.length; i += step) {
        const p = path[i];
        let minDist = Infinity;

        for (const other of otherPaths) {
          // Sample the other path too
          const otherStep = Math.max(1, Math.floor(other.length / 100));
          for (let j = 0; j < other.length; j += otherStep) {
            const dlat = p.lat - other[j].lat;
            const dlng = p.lng - other[j].lng;
            const d = dlat * dlat + dlng * dlng;
            if (d < minDist) minDist = d;
          }
        }

        if (minDist > bestMinDist) {
          bestMinDist = minDist;
          bestPoint = p;
        }
      }

      return { routeIndex: route.route_index, position: bestPoint, duration: route.total_duration_minutes };
    });
  }, [routeData]);

  // Build flat list of all waypoints, selected route first for priority
  const allEntries = useMemo(() => {
    const entries: TaggedWaypoint[] = [];
    const selectedFirst = [...routeData.routes].sort((a, b) => {
      if (a.route_index === selectedRouteIndex) return -1;
      if (b.route_index === selectedRouteIndex) return 1;
      return 0;
    });
    for (const route of selectedFirst) {
      for (let i = 0; i < route.waypoints.length; i++) {
        entries.push({ waypoint: route.waypoints[i], routeIndex: route.route_index, wpIndex: i });
      }
    }
    return entries;
  }, [routeData, selectedRouteIndex]);

  const visibleKeys = useMemo(
    () =>
      map
        ? getVisibleWaypointKeys(allEntries, map, selectedRouteIndex, selectedWaypointIdx)
        : new Set(allEntries.map((e) => `${e.routeIndex}-${e.wpIndex}`)),
    [allEntries, map, selectedRouteIndex, selectedWaypointIdx, zoom],
  );

  // Render weather markers and duration labels for all routes
  return (
    <>
      {/* Duration labels at route midpoints */}
      {routeLabelPositions.map(({ routeIndex, position, duration }) => {
        const isSelected = routeIndex === selectedRouteIndex;
        const dimmed = selectedRouteIndex !== null && !isSelected;
        const isRecommended = routeIndex === recommendedRouteIndex;

        return (
          <AdvancedMarker
            key={`duration-${routeIndex}`}
            position={position}
            zIndex={10}
            onClick={() => onRouteSelect(routeIndex)}
          >
            <div
              className={`route-duration-label${dimmed ? " route-duration-label-dimmed" : ""}${isRecommended ? " route-duration-label-recommended" : ""}`}
              style={{ transform: `scale(${markerScale})` }}
            >
              {isRecommended && <span className="recommended-star">*</span>}
              {formatDuration(duration)}
            </div>
          </AdvancedMarker>
        );
      })}

      {/* Weather markers, filtered for overlaps */}
      {routeData.routes.map((route) => {
        const isSelected = route.route_index === selectedRouteIndex;
        const dimmed = selectedRouteIndex !== null && !isSelected;

        return route.waypoints.map((wp, wpIdx) => {
          if (!visibleKeys.has(`${route.route_index}-${wpIdx}`) || !wp.weather) return null;

          return (
            <WeatherMarker
              key={`${route.route_index}-${wpIdx}`}
              waypoint={wp}
              useFahrenheit={useFahrenheit}
              isSelected={isSelected && wpIdx === selectedWaypointIdx}
              onSelect={() => {
                onRouteSelect(route.route_index);
                onSelectWaypoint(wpIdx);
              }}
              onDeselect={onDeselectWaypoint}
              scale={dimmed ? markerScale * 0.6 : markerScale}
              dimmed={dimmed}
            />
          );
        });
      })}
    </>
  );
}

export default function RouteMap({
  routeData,
  selectedRouteIndex,
  recommendedRouteIndex,
  onRouteSelect,
  useFahrenheit,
  selectedWaypointIdx,
  onSelectWaypoint,
  onDeselectWaypoint,
}: Props) {
  return (
    <Map
      defaultCenter={{ lat: 39.8283, lng: -98.5795 }}
      defaultZoom={4}
      mapId="route-weather-map"
      style={{ width: "100%", height: "100%" }}
    >
      {routeData && (
        <RoutesOverlay
          routeData={routeData}
          selectedRouteIndex={selectedRouteIndex}
          recommendedRouteIndex={recommendedRouteIndex}
          onRouteSelect={onRouteSelect}
          useFahrenheit={useFahrenheit}
          selectedWaypointIdx={selectedWaypointIdx}
          onSelectWaypoint={onSelectWaypoint}
          onDeselectWaypoint={onDeselectWaypoint}
        />
      )}
    </Map>
  );
}
