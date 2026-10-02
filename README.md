# Roam

Roam is a natural-language real-world decision engine for choosing places.

## Current Slice

- FastAPI backend with live OpenStreetMap place providers and seeded Lagos fallback data.
- Natural-language parser for common constraints such as budget, quiet, Wi-Fi, power, duration, date intent, and distance.
- Deterministic scoring engine with match reasons and tradeoffs.
- React + Vite frontend showing the interpreted request, ranked places, and what-if recalculation controls.
- Browser geolocation support for real "near me" searches.

## Data Sources

Roam fetches real place names, categories, and coordinates from OpenStreetMap using Overpass first and Nominatim as a second live source. If live providers are unavailable or too sparse, the API falls back to local seeded Lagos data.

OpenStreetMap does not reliably provide decision attributes like Wi-Fi quality, noise level, price, power access, or ambience, so Roam uses conservative category heuristics for those fields and marks live results with `data_source: OpenStreetMap` plus `details limited` tags.

## Run Locally

Backend:

```bash
PYTHONPATH=backend python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Frontend:

```bash
cd frontend
npm install
npm run dev -- --port 5173
```

Build frontend:

```bash
cd frontend
npm run build
```

Run backend tests once pytest is installed:

```bash
PYTHONPATH=backend python3 -m pytest backend/tests
```
