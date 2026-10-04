from enum import Enum
from math import asin, cos, radians, sin, sqrt
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


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
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)


class Intent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    activity: Activity = Activity.general
    place_types: list[str] = Field(default_factory=list)
    area: str | None = None
    budget_max: int | None = Field(default=None, ge=0, le=10000000)
    duration_hours: float | None = Field(default=None, gt=0, le=48)
    max_minutes: int | None = Field(default=None, gt=0, le=240)
    quiet: bool = False
    wifi: bool = False
    power: bool = False
    open_now: bool = False
    romantic: bool = False
    cheap: bool = False
    must_have: list[str] = Field(default_factory=list)
    avoid: list[str] = Field(default_factory=list)
    priority: list[str] = Field(default_factory=list)
    interpretation: str = ""
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
    photo_url: str | None = None
    photo_page_url: str | None = None


class SearchRequest(BaseModel):
    query: str = Field(min_length=2, max_length=280)
    location: Location | None = None

    @field_validator("query", mode="before")
    @classmethod
    def strip_query(cls, value: str) -> str:
        return value.strip()


class IntentChange(BaseModel):
    model_config = ConfigDict(extra="forbid")
    budget_max: int | None = Field(default=None, ge=0, le=10000000)
    max_minutes: int | None = Field(default=None, gt=0, le=240)
    quiet: bool | None = None
    wifi: bool | None = None
    power: bool | None = None
    open_now: bool | None = None
    romantic: bool | None = None
    cheap: bool | None = None
    priority: list[Literal["distance", "budget", "quiet", "wifi", "ambience", "food"]] | None = None

    @model_validator(mode="after")
    def disallow_null_switches(self):
        for key in self.model_fields_set - {"budget_max", "max_minutes"}:
            if getattr(self, key) is None:
                raise ValueError(f"{key} cannot be null")
        return self


class RefineRequest(BaseModel):
    search_id: str = Field(max_length=64)
    change: IntentChange = Field(default_factory=IntentChange)
    query: str | None = Field(default=None, min_length=2, max_length=280)

    @field_validator("search_id", "query", mode="before")
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else value

    @model_validator(mode="after")
    def require_query_or_change(self):
        if self.query is None and not self.change.model_fields_set:
            raise ValueError("query or change is required")
        return self


class Evidence(BaseModel):
    label: str
    value: str
    status: Literal["listed", "estimated", "unknown", "demo"]


class ReviewOpinion(BaseModel):
    source: Literal["Google reviews"]
    rating: float | None = Field(default=None, ge=0, le=5)
    review_count: int | None = Field(default=None, ge=0)
    sample_size: int = Field(ge=1)
    opinion: str = Field(min_length=1, max_length=300)
    praise: list[str] = Field(default_factory=list, max_length=3)
    cautions: list[str] = Field(default_factory=list, max_length=3)
    reviews_url: str | None = None


class Result(BaseModel):
    place_id: str
    name: str
    category: str
    area: str
    score: int
    rating: float | None
    price_level: int
    typical_spend: int
    distance_km: float | None = None
    travel_minutes: int | None = None
    open_now: bool | None
    match_reasons: list[str]
    tradeoffs: list[str]
    tags: list[str]
    data_source: str = "seed"
    photo_url: str | None = None
    photo_page_url: str | None = None
    maps_url: str = ""
    photos_url: str = ""
    evidence: list[Evidence] = Field(default_factory=list)
    review_opinion: ReviewOpinion | None = None


class DecisionInsight(BaseModel):
    headline: str
    summary: str
    confidence: Literal["high", "medium", "low"]
    primary_tradeoff: str
    next_best_action: str
    caveats: list[str]


class SearchResponse(BaseModel):
    search_id: str = Field(default_factory=lambda: uuid4().hex)
    intent: Intent
    intelligence: DecisionInsight
    results: list[Result]
    engine: Literal["ai", "rules"] = "rules"
    engine_status: str = "Basic understanding"
    suggestions: list[str] = Field(default_factory=list)
    clarification: str | None = None
    data_status: Literal["live", "demo", "unavailable"] = "live"
    locality_note: str | None = None


def distance_km(origin: Location, destination: Location) -> float:
    earth_radius_km = 6371
    d_lat = radians(destination.lat - origin.lat)
    d_lng = radians(destination.lng - origin.lng)
    lat1 = radians(origin.lat)
    lat2 = radians(destination.lat)
    value = sin(d_lat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(d_lng / 2) ** 2
    return 2 * earth_radius_km * asin(sqrt(value))
