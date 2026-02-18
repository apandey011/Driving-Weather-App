# Route Weather

A full-stack web application that finds the best driving route between two locations based on real-time weather conditions along the way. It fetches multiple route alternatives from Google Maps, samples weather at 15-minute intervals along each route, and uses an ML model to score and recommend the safest/most comfortable route.

## Tech Stack

**Frontend:** React 18, TypeScript, Vite 6, Google Maps (`@vis.gl/react-google-maps`), polyline codec
**Backend:** Python, FastAPI 0.115, Uvicorn, HTTPX (async HTTP), Pydantic 2, scikit-learn (Gradient Boosting)
**External APIs:** Google Directions API (route planning), Open-Meteo API (weather forecasts, free/no auth)

## Project Structure

```
├── .github/workflows/ci.yml          # GitHub Actions CI (tests + e2e)
├── .nvmrc                            # Node.js version (20)
├── .python-version                   # Python version (3.12)
│
├── frontend/                         # React + TypeScript SPA
│   ├── src/
│   │   ├── main.tsx                  # Entry point (React 18 createRoot)
│   │   ├── App.tsx                   # Root component, holds all state
│   │   ├── App.css                   # All styles (single file)
│   │   ├── api.ts                    # Backend API client (POST /api/route-weather)
│   │   ├── types.ts                  # TypeScript interfaces for API responses
│   │   ├── utils.ts                  # Shared utility functions (temp conversion, formatting)
│   │   ├── test/
│   │   │   ├── setup.ts             # Vitest setup (localStorage polyfill, Google Maps mock)
│   │   │   └── fixtures.ts          # Shared test fixtures
│   │   └── components/
│   │       ├── LocationForm.tsx      # Origin/destination inputs + departure time
│   │       ├── PlaceAutocomplete.tsx # Google Places autocomplete wrapper
│   │       ├── RecentRoutes.tsx      # Recent route history (localStorage)
│   │       ├── RouteMap.tsx          # Map with polylines, markers, duration labels
│   │       ├── RouteRecommendationBanner.tsx # Route recommendation display
│   │       ├── WeatherPanel.tsx      # Right sidebar: scrollable weather per waypoint
│   │       ├── WeatherAdvisories.tsx # Weather advisory alerts
│   │       ├── WeatherMarker.tsx     # Map marker showing emoji + temp
│   │       ├── WeatherCard.tsx       # InfoWindow with full weather details
│   │       └── TempToggle.tsx        # Celsius/Fahrenheit switch
│   ├── e2e/
│   │   └── smoke.spec.ts            # Playwright e2e smoke test
│   ├── playwright.config.ts          # Playwright configuration
│   ├── package.json
│   ├── vite.config.ts                # Vite + Vitest config
│   ├── tsconfig.json
│   └── .env                          # VITE_GOOGLE_MAPS_API_KEY
│
├── backend/                          # Python FastAPI service
│   ├── app/
│   │   ├── main.py                   # FastAPI app setup, CORS, router mount
│   │   ├── config.py                 # Pydantic Settings (env vars)
│   │   ├── models.py                 # All Pydantic request/response models
│   │   ├── routes.py                 # Single POST endpoint handler
│   │   ├── services/
│   │   │   ├── directions.py         # Google Directions API client
│   │   │   ├── weather.py            # Open-Meteo API client (async, semaphore-limited)
│   │   │   ├── sampling.py           # 15-minute waypoint interpolation along route
│   │   │   └── scoring.py            # ML scoring + rule-based weather advisories
│   │   └── ml/
│   │       ├── train_model.py        # Gradient Boosting model training (synthetic data)
│   │       └── route_model.joblib    # Pre-trained model artifact
│   ├── tests/
│   │   ├── conftest.py               # Shared fixtures (mock settings, test client)
│   │   ├── test_cache.py
│   │   ├── test_config.py
│   │   ├── test_directions.py
│   │   ├── test_models.py
│   │   ├── test_routes.py
│   │   ├── test_sampling.py
│   │   ├── test_scoring.py
│   │   └── test_weather.py
│   ├── pytest.ini
│   ├── requirements.txt
│   └── .env                          # GOOGLE_MAPS_API_KEY, FRONTEND_ORIGIN
│
└── CLAUDE.md                         # This file
```

## Running the Project

### Environment Variables

| Variable | Location | Description |
|---|---|---|
| `GOOGLE_MAPS_API_KEY` | backend `.env` | Google Cloud API key (Directions API enabled) |
| `VITE_GOOGLE_MAPS_API_KEY` | frontend `.env` | Same key, exposed to Vite |
| `FRONTEND_ORIGIN` | backend `.env` | CORS origin, defaults to `http://localhost:5173` |

### Backend (runs on port 8000)

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Frontend (runs on port 5173)

```bash
cd frontend
npm install
npm run dev
```

### Build

```bash
cd frontend
npm run build    # runs tsc -b && vite build, outputs to dist/
```

### Testing

```bash
# Backend (98 tests) — pytest + pytest-asyncio + respx
cd backend
python -m pytest

# Frontend unit tests (94 tests) — Vitest + React Testing Library
cd frontend
npm test

# Frontend e2e smoke test — Playwright (requires browsers: npx playwright install)
cd frontend
npm run test:e2e
```

CI runs automatically on push to `main` and on pull requests via GitHub Actions (`.github/workflows/ci.yml`).

## API 

Single endpoint: **POST `/api/route-weather`**

**Request:**
```json
{
  "origin": "San Francisco, CA",
  "destination": "Los Angeles, CA",
  "departure_time": "2026-02-16T10:00:00Z"  // optional, defaults to now
}
```

**Response:**
```json
{
  "origin_address": "San Francisco, CA, USA",
  "destination_address": "Los Angeles, CA, USA",
  "routes": [
    {
      "route_index": 0,
      "overview_polyline": "encoded_string",
      "summary": "via I-5 S",
      "total_duration_minutes": 350.5,
      "total_distance_km": 612.3,
      "waypoints": [
        {
          "location": { "lat": 37.77, "lng": -122.42 },
          "minutes_from_start": 0,
          "estimated_time": "2026-02-16T10:00:00Z",
          "weather": {
            "temperature_c": 15.2,
            "apparent_temperature_c": 13.8,
            "precipitation_mm": 0.0,
            "precipitation_probability": 10,
            "weather_code": 1,
            "weather_description": "Mainly clear",
            "wind_speed_kmh": 12.5,
            "humidity_percent": 65
          }
        }
      ]
    }
  ],
  "recommendation": {
    "recommended_route_index": 0,
    "scores": [ { "route_index": 0, "overall_score": 85.2, "duration_score": 90, "weather_score": 80 } ],
    "advisories": [ { "route_index": 1, "message": "Heavy rain expected", "severity": "warning" } ]
  }
}
```

## Architecture & Data Flow

### End-to-End Flow

1. User enters origin, destination, and optional departure time in `LocationForm`
2. Frontend calls `POST /api/route-weather` via `api.ts`
3. Backend `routes.py` handler orchestrates:
   - **Directions service** → fetches 3+ route alternatives from Google Directions API
   - **Sampling service** → interpolates waypoints every 15 minutes along each route using Haversine distance + polyline decoding
   - **Weather service** → fetches hourly forecasts from Open-Meteo for each waypoint (deduplicates by rounding lat/lng to 2 decimal places + hour)
   - **Scoring service** → runs ML model to score routes 0-100, generates rule-based advisories
4. Frontend receives all routes with weather data
5. `RouteMap` renders polylines and weather markers on Google Maps
6. `WeatherPanel` shows scrollable weather breakdown for selected route

### Backend Architecture (Layered)

```
routes.py (endpoint handler)
  ├── services/directions.py  → Google Directions API
  ├── services/sampling.py    → waypoint interpolation (pure logic)
  ├── services/weather.py     → Open-Meteo API (async, 5-concurrent limit)
  └── services/scoring.py     → ML model + advisory rules
```

### Frontend Component Hierarchy

```
App (all state lives here)
  ├── TempToggle
  ├── LocationForm
  │   └── PlaceAutocomplete (x2, forwardRef)
  ├── RouteMap
  │   └── RoutesOverlay (renders polylines + markers)
  │       └── WeatherMarker (opens WeatherCard in InfoWindow)
  └── WeatherPanel (scrollable sidebar)
```

State management: React `useState`/`useRef`/`useMemo`/`useEffect` only. No external state library. All state in `App.tsx`, passed via props.

## ML Model

**Type:** Gradient Boosting Regressor (scikit-learn), 200 estimators, max depth 4
**Training:** 5,000 synthetic samples generated in `train_model.py`
**Artifact:** `backend/app/ml/route_model.joblib`

**9-Feature Vector:**
1. `duration_ratio` — route duration / fastest route
2. `avg_weather_severity` — mean WMO severity (0-1 scale)
3. `max_weather_severity` — worst WMO severity on route
4. `avg_wind_speed` — mean wind (km/h)
5. `max_wind_speed` — peak wind
6. `avg_precipitation` — mean rainfall (mm)
7. `max_precipitation` — peak rainfall
8. `pct_adverse_waypoints` — fraction of waypoints with WMO code >= 61
9. `avg_precip_probability` — mean precipitation chance (0-100%)

**Output:** 0-100 desirability score (higher = better route)

**Advisory Rules** (in `scoring.py`, rule-based, not ML):
- Heavy rain/snow/thunderstorms/hail → "danger" severity
- Moderate rain/snow, fog, high winds → "warning" severity
- Wind thresholds: 50+ km/h warning, 75+ km/h danger

## Key Conventions

- **Pydantic everywhere:** All backend data shapes defined as Pydantic `BaseModel` in `models.py`
- **Async weather fetching:** `weather.py` uses `asyncio.Semaphore(5)` to limit concurrent Open-Meteo requests
- **Weather deduplication:** Waypoints grouped by `(round(lat,2), round(lng,2), hour)` to avoid redundant API calls across routes
- **Polyline encoding:** Routes stored as Google encoded polylines, decoded on frontend with `@googlemaps/polyline-codec` and on backend with `polyline` library
- **Marker density management:** `RouteMap` hides overlapping markers based on pixel distance at current zoom level
- **Temperature conversion:** Done in frontend components, backend always returns Celsius
- **No routing library:** Single-page app, no client-side navigation
- **Testing:** Frontend uses Vitest + React Testing Library (unit) and Playwright (e2e); backend uses pytest + pytest-asyncio + respx. Test files live alongside source (`*.test.ts(x)`) or in `backend/tests/`. CI via GitHub Actions.
- **CSS:** Single `App.css` file with global classes, blue color scheme (#1a73e8 primary)
- **WMO weather codes:** Standard meteorological codes mapped to descriptions and emojis in both frontend and backend
