import { useEffect, useRef, useState } from "react";
import { APIProvider } from "@vis.gl/react-google-maps";
import { fetchRouteWeather } from "./api";
import { MultiRouteResponse } from "./types";
import LocationForm, { LocationFormHandle } from "./components/LocationForm";
import { loadHistory, saveToHistory, RecentRoute } from "./components/RecentRoutes";
import RouteMap from "./components/RouteMap";
import RouteRecommendationBanner from "./components/RouteRecommendationBanner";
import TempToggle from "./components/TempToggle";
import WeatherPanel from "./components/WeatherPanel";

const GOOGLE_MAPS_API_KEY = import.meta.env.VITE_GOOGLE_MAPS_API_KEY || "";
const E2E_MODE = import.meta.env.VITE_E2E_MODE === "1";

export default function App() {
  const [routeData, setRouteData] = useState<MultiRouteResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [useFahrenheit, setUseFahrenheit] = useState(true);
  const [selectedRouteIndex, setSelectedRouteIndex] = useState<number | null>(null);
  const [selectedWaypointIdx, setSelectedWaypointIdx] = useState<number | null>(null);
  const [linkCopied, setLinkCopied] = useState(false);
  const [recentHistory, setRecentHistory] = useState<RecentRoute[]>(loadHistory());

  const formRef = useRef<LocationFormHandle>(null);
  const lastSubmitRef = useRef<{
    origin: string;
    destination: string;
    departureTime?: string;
  } | null>(null);

  const selectedRoute =
    routeData && selectedRouteIndex !== null
      ? routeData.routes[selectedRouteIndex]
      : null;

  // Auto-fill from URL params on mount
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const from = params.get("from");
    const to = params.get("to");
    const depart = params.get("depart") || undefined;
    if (from && to) {
      setTimeout(() => {
        formRef.current?.fillAndSubmit(from, to, from, to, depart);
      }, 0);
    }
  }, []);

  async function handleSubmit(
    origin: string,
    destination: string,
    departureTime?: string,
    originDisplay?: string,
    destinationDisplay?: string
  ) {
    lastSubmitRef.current = { origin, destination, departureTime };
    setLoading(true);
    setError(null);
    setSelectedRouteIndex(null);
    setSelectedWaypointIdx(null);
    try {
      const data = await fetchRouteWeather(origin, destination, departureTime);
      setRouteData(data);
      if (data.recommendation) {
        setSelectedRouteIndex(data.recommendation.recommended_route_index);
      }

      // Save to recent history
      const entry: RecentRoute = {
        origin,
        destination,
        originDisplay: originDisplay || data.origin_address,
        destinationDisplay: destinationDisplay || data.destination_address,
        timestamp: Date.now(),
      };
      saveToHistory(entry);
      setRecentHistory(loadHistory());

      // Update URL for sharing
      const params = new URLSearchParams();
      params.set("from", originDisplay || data.origin_address);
      params.set("to", destinationDisplay || data.destination_address);
      if (departureTime) params.set("depart", departureTime);
      window.history.replaceState(null, "", `?${params.toString()}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setLoading(false);
    }
  }

  function handleRetry() {
    if (lastSubmitRef.current) {
      const { origin, destination, departureTime } = lastSubmitRef.current;
      handleSubmit(origin, destination, departureTime);
    }
  }

  function handleRouteSelect(index: number) {
    setSelectedRouteIndex(index);
    setSelectedWaypointIdx(null);
  }

  const appContent = (
    <div className="app">
      <header className="app-header">
        <div className="header-left">
          <h1>Route Weather by Aadi Pandey</h1>
          <p>See the weather along your drive at 15-minute intervals</p>
        </div>
        <TempToggle
          useFahrenheit={useFahrenheit}
          onToggle={() => setUseFahrenheit((f) => !f)}
        />
      </header>

      <LocationForm ref={formRef} onSubmit={handleSubmit} loading={loading} recentHistory={recentHistory} />

      {error && (
        <div className="error-banner">
          <span className="error-message">{error}</span>
          <div className="error-actions">
            <button className="error-retry-btn" onClick={handleRetry}>Retry</button>
            <button className="error-dismiss-btn" onClick={() => setError(null)} aria-label="Dismiss">&times;</button>
          </div>
        </div>
      )}

      {routeData && (
        <div className="route-summary">
          <span>
            {routeData.origin_address} &rarr; {routeData.destination_address}
          </span>
          <div className="route-summary-actions">
            {selectedRoute && (
              <span>
                {selectedRoute.summary && `${selectedRoute.summary} · `}
                {selectedRoute.total_duration_minutes} min &middot;{" "}
                {selectedRoute.total_distance_km} km
              </span>
            )}
            <button
              className="copy-link-btn"
              onClick={() => {
                navigator.clipboard.writeText(window.location.href).then(() => {
                  setLinkCopied(true);
                  setTimeout(() => setLinkCopied(false), 2000);
                });
              }}
            >
              {linkCopied ? "Copied!" : "Copy Link"}
            </button>
          </div>
        </div>
      )}

      {routeData && routeData.recommendation && (
        <RouteRecommendationBanner
          recommendation={routeData.recommendation}
          routes={routeData.routes}
          selectedRouteIndex={selectedRouteIndex}
          onRouteSelect={handleRouteSelect}
        />
      )}

      <div className="main-content">
        {loading && (
          <div className="loading-overlay">
            <div className="loading-spinner" />
            <p className="loading-text">Finding routes and weather...</p>
          </div>
        )}
        <div className="map-container">
          {E2E_MODE ? (
            <div data-testid="e2e-route-map" style={{ minHeight: 1, minWidth: 1 }} />
          ) : (
            <RouteMap
              routeData={routeData}
              selectedRouteIndex={selectedRouteIndex}
              recommendedRouteIndex={routeData?.recommendation?.recommended_route_index ?? null}
              onRouteSelect={handleRouteSelect}
              useFahrenheit={useFahrenheit}
              selectedWaypointIdx={selectedWaypointIdx}
              onSelectWaypoint={setSelectedWaypointIdx}
              onDeselectWaypoint={() => setSelectedWaypointIdx(null)}
            />
          )}
        </div>
        {selectedRoute && (
          <WeatherPanel
            waypoints={selectedRoute.waypoints}
            useFahrenheit={useFahrenheit}
            onSelectWaypoint={setSelectedWaypointIdx}
            onClose={() => { setSelectedRouteIndex(null); setSelectedWaypointIdx(null); }}
            advisories={
              routeData?.recommendation && selectedRouteIndex !== null
                ? routeData.recommendation.advisories[selectedRouteIndex] ?? []
                : []
            }
          />
        )}
      </div>
    </div>
  );

  if (E2E_MODE) {
    return appContent;
  }

  return (
    <APIProvider apiKey={GOOGLE_MAPS_API_KEY}>
      {appContent}
    </APIProvider>
  );
}
