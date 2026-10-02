# Roam

Roam is a natural-language real-world decision engine for choosing places.

## Current Slice

- FastAPI backend with seeded Lagos places.
- Natural-language parser for common constraints such as budget, quiet, Wi-Fi, power, duration, date intent, and distance.
- Deterministic scoring engine with match reasons and tradeoffs.
- React + Vite frontend showing the interpreted request, ranked places, and what-if recalculation controls.

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
