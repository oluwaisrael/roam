# Roam

Roam is a natural-language real-world decision engine for choosing places.

## Current Slice

- FastAPI backend with live OpenStreetMap place providers and seeded Lagos fallback data.
- Natural-language parser for common constraints such as budget, quiet, Wi-Fi, power, duration, date intent, and distance.
- Deterministic scoring engine with match reasons and tradeoffs.
- Deterministic intelligence layer with recommendation summaries, confidence, caveats, and next-best actions.
- React + Vite frontend showing the interpreted request, ranked places, and what-if recalculation controls.
- Browser geolocation support for real "near me" searches.
- Place photo fields and a redirect path for verified OSM/Wikimedia image sources when available.

## Data Sources

Roam fetches real place names, categories, and coordinates from OpenStreetMap using Overpass first and Nominatim as a second live source. If live providers are unavailable or too sparse, the API falls back to local seeded Lagos data.

OpenStreetMap does not reliably provide decision attributes like Wi-Fi quality, noise level, price, power access, or ambience, so Roam uses conservative category heuristics for those fields and marks live results with `data_source: OpenStreetMap` plus `details limited` tags.

## Review Intelligence

If `GOOGLE_PLACES_API_KEY` is configured with Places API (New), Roam enriches the top three local results with an attributed opinion based on the review text returned for the matched venue. It shows the sample size, rating when available, recurring praise/cautions, and a link to the reviews. It does not invent an opinion when no review text is available.

Demo fallback data is opt-in through `ROAM_DEMO_DATA=true`. Without that setting, live provider failure returns an honest unavailable state instead of silently mixing demo places into a real search.

When OSM includes `image`, `wikimedia_commons`, or `wikidata` tags, results include `photo_url` and/or `photo_page_url`. Recent search results can also redirect through:

```text
/api/search/{search_id}/places/{place_id}/photo
```

## Understanding

Roam can use a language model to turn a natural-language request into structured intent, while retrieval, ranking, evidence, and recommendations stay deterministic. Set `ROAM_AI_PROVIDER=openai` with `OPENAI_API_KEY`, or use `ROAM_AI_PROVIDER=ollama` with a local Ollama server. If no provider is configured or a provider fails, Roam falls back to the rules parser and still returns clarification prompts when a request needs verification.

Copy `.env.example` for the supported environment variables.

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
