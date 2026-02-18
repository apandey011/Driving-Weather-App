# Route Weather

> **Live demo:** [aadipandey.com](https://aadipandey.com)

A full-stack web application that finds the best driving route between two locations based on real-time weather conditions. It fetches multiple route alternatives from Google Maps, samples weather at 15-minute intervals along each route, and uses a machine learning model to score and recommend the safest route.


## How It Works

1. User enters origin, destination, and optional departure time
2. Backend fetches route alternatives from Google Directions API
3. Waypoints are interpolated every 15 minutes along each route using Haversine distance
4. Weather forecasts are fetched asynchronously from Open-Meteo for each waypoint (deduplicated by location + hour)
5. ML model scores each route on a 0-100 scale; rule-based engine generates safety advisories
6. Frontend displays routes on an interactive map with weather overlays and a scrollable weather panel

## Features

- **Multi-route comparison** — Fetches 3+ route alternatives from Google Directions API
- **Weather-aware routing** — Samples weather conditions every 15 minutes along each route using Open-Meteo
- **ML-powered scoring** — Gradient Boosting model scores routes 0-100 based on weather severity, wind, precipitation, and duration
- **Interactive map** — Google Maps with color-coded polylines, weather markers with emoji indicators, and clickable detail cards
- **Safety advisories** — Rule-based alerts for dangerous conditions (heavy rain, snow, thunderstorms, high winds)
- **Temperature toggle** — Switch between Celsius and Fahrenheit

## Architecture

```
React SPA ──POST /api/route-weather──▶ FastAPI
        ├── Google Directions API → 3+ route alternatives
        ├── Haversine interpolation → waypoints every 15 min
        ├── Open-Meteo API (async, 5 concurrent) → hourly forecasts
        └── ML scoring + rule-based advisories → ranked routes
```

### Technical Highlights

- **Async pipeline** — Backend orchestrates multiple external API calls concurrently using `asyncio` with semaphore-limited parallelism (5 concurrent weather requests)
- **Smart deduplication** — Waypoints are grouped by `(lat, lng, hour)` rounded to 2 decimal places, eliminating redundant weather API calls across overlapping routes
- **ML model** — Gradient Boosting Regressor (scikit-learn, 200 estimators) trained on a 9-feature vector including duration ratio, weather severity, wind speed, precipitation, and adverse waypoint percentage
- **Marker density management** — Frontend dynamically hides overlapping weather markers based on pixel distance at the current zoom level
- **Multi-stage Docker build** — Node.js stage compiles the frontend; Python stage serves both API and static files from a single container
- **SPA-ready backend** — FastAPI conditionally serves the built frontend with catch-all routing, while remaining unaffected in local development

## Tech Stack

| Layer | Technologies |
|-------|-------------|
| Frontend | React 18, TypeScript, Vite 6, Google Maps (`@vis.gl/react-google-maps`) |
| Backend | Python, FastAPI, Uvicorn, HTTPX (async), Pydantic 2 |
| ML | scikit-learn Gradient Boosting Regressor |
| Infrastructure | Docker (multi-stage), Railway |
| APIs | Google Directions API, Open-Meteo API |

## Getting Started

### Prerequisites

- Node.js 20 (see `.nvmrc`)
- Python 3.12 (see `.python-version`)
- Google Cloud API key with Maps JavaScript API, Places API, and Directions API enabled

### Local Development

```bash
git clone https://github.com/apandey011/claude-test.git
cd claude-test
```

Create `backend/.env`:
```
GOOGLE_MAPS_API_KEY=your_google_api_key
FRONTEND_ORIGIN=http://localhost:5173
```

Create `frontend/.env`:
```
VITE_GOOGLE_MAPS_API_KEY=your_google_api_key
VITE_API_BASE=http://localhost:8000
```

Start the backend and frontend in separate terminals:

```bash
# Terminal 1 — Backend (port 8000)
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload

# Terminal 2 — Frontend (port 5173)
cd frontend
npm install
npm run dev
```

### Testing

```bash
# Backend tests (pytest)
cd backend && python -m pytest

# Frontend unit tests (Vitest)
cd frontend && npm test

# Frontend e2e smoke test (Playwright — install browsers first: npx playwright install)
cd frontend && npm run test:e2e
```

CI runs automatically on push to `main` and on pull requests via [GitHub Actions](.github/workflows/ci.yml).

### Docker

```bash
docker build --build-arg VITE_GOOGLE_MAPS_API_KEY=your_key -t route-weather .
docker run -p 8000:8000 -e GOOGLE_MAPS_API_KEY=your_key route-weather
```

### Deployment (Railway)

The project deploys as a single service on Railway using the included `Dockerfile`. Set `GOOGLE_MAPS_API_KEY` (runtime) and `VITE_GOOGLE_MAPS_API_KEY` (build arg) in the Railway dashboard.

## API

**POST** `/api/route-weather`

```json
{
  "origin": "San Francisco, CA",
  "destination": "Los Angeles, CA",
  "departure_time": "2026-02-16T10:00:00Z"
}
```

Returns multiple scored routes with per-waypoint weather data, a recommended route index, composite scores, and safety advisories.

## License

MIT
