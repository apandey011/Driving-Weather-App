import { MultiRouteResponse } from "./types";

const API_BASE = import.meta.env.VITE_API_BASE || "";

function normalizeDepartureTime(departureTime?: string): string | null {
  if (!departureTime) return null;

  const value = departureTime.trim();
  if (!value) return null;

  const hasTimezoneInfo = /(Z|[+-]\d{2}:\d{2})$/i.test(value);
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    throw new Error("Invalid departure time format");
  }

  // Already timezone-aware ISO-ish value: keep as-is.
  if (hasTimezoneInfo) {
    return value;
  }

  // Naive datetime-local value: interpret as local time and convert to UTC.
  return parsed.toISOString();
}

export async function fetchRouteWeather(
  origin: string,
  destination: string,
  departureTime?: string
): Promise<MultiRouteResponse> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 60000);

  try {
    const response = await fetch(`${API_BASE}/api/route-weather`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        origin,
        destination,
        departure_time: normalizeDepartureTime(departureTime),
      }),
      signal: controller.signal,
    });

    if (!response.ok) {
      let message = "Failed to fetch route weather";
      try {
        const error = await response.json();
        message = error.detail || message;
      } catch {
        // response body wasn't JSON
      }
      throw new Error(message);
    }

    return response.json();
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") {
      throw new Error("Request timed out — please try again");
    }
    throw err;
  } finally {
    clearTimeout(timeout);
  }
}
