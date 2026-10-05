from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime
import os
from zoneinfo import ZoneInfo

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from app.intelligence import explain_decision
from app.models import Activity, Intent, Location, RefineRequest, Result, SearchRequest, SearchResponse
from app.providers import CompositePlaceProvider, NominatimPlaceProvider, OverpassPlaceProvider, SeedPlaceProvider, area_center
from app.query_parser import normalize_intent
from app.reviews import enrich_with_reviews
from app.scoring import local_distance_limit_km, score_places
from app.understanding import understand

app = FastAPI(title="Roam API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=os.getenv("ROAM_CORS_ORIGIN_REGEX", r"http://(localhost|127\.0\.0\.1):51\d{2}"),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@dataclass
class SearchContext:
    query: str
    intent: Intent
    location: Location | None


MAX_MEMORY_ITEMS = 200
SEARCH_MEMORY: OrderedDict[str, SearchContext] = OrderedDict()
PHOTO_MEMORY: OrderedDict[str, dict[str, str]] = OrderedDict()
PLACE_PROVIDER = CompositePlaceProvider([OverpassPlaceProvider(), NominatimPlaceProvider()], SeedPlaceProvider())
LAGOS_TIMEZONE = ZoneInfo("Africa/Lagos")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "version": app.version,
        "ai_provider": os.getenv("ROAM_AI_PROVIDER", "openai" if os.getenv("OPENAI_API_KEY") else "rules"),
        "demo_data": os.getenv("ROAM_DEMO_DATA", "false").lower(),
    }


@app.post("/api/search", response_model=SearchResponse)
def search(request: SearchRequest) -> SearchResponse:
    intent, engine, engine_status, clarification = understand(request.query)
    return _run_search(request.query, intent, request.location, engine, engine_status, clarification)


@app.post("/api/search/refine", response_model=SearchResponse)
def refine(request: RefineRequest) -> SearchResponse:
    if request.search_id not in SEARCH_MEMORY:
        raise HTTPException(status_code=404, detail="Search not found")

    context = SEARCH_MEMORY[request.search_id]
    query = request.query or context.query
    if request.query:
        intent, engine, engine_status, clarification = understand(request.query, context.intent)
    else:
        intent = context.intent.model_copy(deep=True)
        engine = "rules"
        engine_status = "Refined with explicit controls"
        clarification = None
    changes = request.change.model_dump(exclude_unset=True)
    if changes:
        intent = normalize_intent(Intent.model_validate({**intent.model_dump(), **changes}), query)

    return _run_search(query, intent, context.location, engine, engine_status, clarification)


def _run_search(
    query: str,
    intent: Intent,
    location: Location | None,
    engine: str,
    engine_status: str,
    clarification: str | None,
) -> SearchResponse:
    places = PLACE_PROVIDER.search(intent, location)
    scoring_origin = area_center(intent) if intent.area else location
    results = score_places(places, intent, scoring_origin, at_hour=_current_lagos_hour())[:6]
    results = enrich_with_reviews(results)
    response = SearchResponse(
        intent=intent,
        intelligence=explain_decision(intent, results),
        results=results,
        engine=engine,
        engine_status=engine_status,
        suggestions=_suggestions(intent, results),
        clarification=clarification,
        data_status=_data_status(results),
        locality_note=_locality_note(intent, location),
    )
    _remember(response.search_id, SearchContext(query=query, intent=intent, location=location), _photo_links(results))
    return response


def _current_lagos_hour() -> int:
    return datetime.now(LAGOS_TIMEZONE).hour


def _remember(search_id: str, context: SearchContext, photo_links: dict[str, str]) -> None:
    SEARCH_MEMORY[search_id] = context
    PHOTO_MEMORY[search_id] = photo_links
    while len(SEARCH_MEMORY) > MAX_MEMORY_ITEMS:
        old_search_id, _ = SEARCH_MEMORY.popitem(last=False)
        PHOTO_MEMORY.pop(old_search_id, None)
    while len(PHOTO_MEMORY) > MAX_MEMORY_ITEMS:
        PHOTO_MEMORY.popitem(last=False)


def _suggestions(intent: Intent, results: list[Result]) -> list[str]:
    suggestions: list[str] = []
    if intent.budget_max is None:
        suggestions.append("Add a budget, e.g. under ₦15k")
    if intent.max_minutes is None:
        suggestions.append("Set a travel limit, e.g. within 15 minutes")
    if not intent.area and not results:
        suggestions.append("Name an area like Yaba, Ikoyi, VI, or Lekki")
    if intent.activity == Activity.work and not intent.power:
        suggestions.append("Say if power sockets matter")
    if results and any(result.data_source != "seed" for result in results):
        suggestions.append("Open the map or photo links to confirm live details")
    return suggestions[:3]


def _data_status(results: list[Result]) -> str:
    if not results:
        return "unavailable"
    if all(result.data_source == "seed" for result in results):
        return "demo"
    return "live"


def _locality_note(intent: Intent, location: Location | None) -> str | None:
    limit = local_distance_limit_km(intent, location)
    if limit is None:
        return None
    return f"Showing places within about {limit:g} km of your current location"


@app.get("/api/search/{search_id}/places/{place_id}/photo")
def place_photo(search_id: str, place_id: str) -> RedirectResponse:
    photo_url = PHOTO_MEMORY.get(search_id, {}).get(place_id)
    if not photo_url:
        raise HTTPException(status_code=404, detail="No verified photo path is available for this place")
    return RedirectResponse(photo_url)


def _photo_links(results: list[Result]) -> dict[str, str]:
    links = {}
    for result in results:
        photo_url = result.photo_url or result.photo_page_url
        if photo_url:
            links[result.place_id] = photo_url
    return links
