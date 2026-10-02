from enum import Enum
from math import asin, cos, radians, sin, sqrt
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field


class Activity(str, Enum):
    work = "work"
    date = "date"
    quick_stop = "quick_stop"
    read = "read"
    eat = "eat"
    unwind = "unwind"
    general = "general"


class NoiseLevel(str, Enum):
    quiet = "quiet"
    moderate = "moderate"
    lively = "lively"


class Location(BaseModel):
    lat: float
    lng: float


class Intent(BaseModel):
    activity: Activity = Activity.general
    budget_max: int | None = None
    duration_hours: float | None = None
    max_minutes: int | None = None
    quiet: bool = False
    wifi: bool = False
    power: bool = False
    open_now: bool = False
    romantic: bool = False
    cheap: bool = False
    raw_terms: list[str] = Field(default_factory=list)


class Place(BaseModel):
    id: str
    name: str
    category: str
    area: str
    location: Location
    price_level: Literal[1, 2, 3, 4]
    typical_spend: int
    rating: float
    opens_at: int
    closes_at: int
    wifi: int
    power: int
    quietness: int
    seating: int
    ambience: int
    food: int
    parking: bool
    security: int
    outdoor_seating: bool
    work_friendly: int
    date_friendly: int
    family_friendly: int
    tags: list[str]
    data_source: str = "seed"


class SearchRequest(BaseModel):
    query: str = Field(min_length=2, max_length=280)
    location: Location | None = None


class RefineRequest(BaseModel):
    search_id: str
    change: dict


class Result(BaseModel):
    place_id: str
    name: str
    category: str
    area: str
    score: int
    rating: float
    price_level: int
    typical_spend: int
    distance_km: float | None = None
    travel_minutes: int | None = None
    open_now: bool
    match_reasons: list[str]
    tradeoffs: list[str]
    tags: list[str]
    data_source: str = "seed"


class SearchResponse(BaseModel):
    search_id: str = Field(default_factory=lambda: uuid4().hex)
    intent: Intent
    results: list[Result]


def distance_km(origin: Location, destination: Location) -> float:
    earth_radius_km = 6371
    d_lat = radians(destination.lat - origin.lat)
    d_lng = radians(destination.lng - origin.lng)
    lat1 = radians(origin.lat)
    lat2 = radians(destination.lat)
    value = sin(d_lat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(d_lng / 2) ** 2
    return 2 * earth_radius_km * asin(sqrt(value))
