from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.models import RefineRequest, SearchRequest, SearchResponse
from app.providers import CompositePlaceProvider, NominatimPlaceProvider, OverpassPlaceProvider, SeedPlaceProvider
from app.query_parser import parse_query
from app.scoring import score_places

app = FastAPI(title="Roam API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1):51\d{2}",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SEARCH_MEMORY: dict[str, tuple[str, object]] = {}
PLACE_PROVIDER = CompositePlaceProvider([OverpassPlaceProvider(), NominatimPlaceProvider()], SeedPlaceProvider())


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/search", response_model=SearchResponse)
def search(request: SearchRequest) -> SearchResponse:
    intent = parse_query(request.query)
    places = PLACE_PROVIDER.search(intent, request.location)
    results = score_places(places, intent, request.location)[:6]
    response = SearchResponse(intent=intent, results=results)
    SEARCH_MEMORY[response.search_id] = (request.query, request.location)
    return response


@app.post("/api/search/refine", response_model=SearchResponse)
def refine(request: RefineRequest) -> SearchResponse:
    if request.search_id not in SEARCH_MEMORY:
        raise HTTPException(status_code=404, detail="Search not found")

    query, location = SEARCH_MEMORY[request.search_id]
    intent = parse_query(query)
    for key, value in request.change.items():
        if hasattr(intent, key):
            setattr(intent, key, value)

    places = PLACE_PROVIDER.search(intent, location)
    results = score_places(places, intent, location)[:6]
    response = SearchResponse(intent=intent, results=results)
    SEARCH_MEMORY[response.search_id] = (query, location)
    return response
