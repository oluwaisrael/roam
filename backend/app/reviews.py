"""Optional, source-attributed review enrichment for already-ranked places."""

import json
import os
import re
from collections import OrderedDict
from threading import Lock
from time import monotonic
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.models import Result, ReviewOpinion

PLACES_TEXT_SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"
CACHE_TTL_SECONDS = 900
MAX_ENRICHED_RESULTS = 3

POSITIVE_TOPICS = {
    "food": ("food", "meal", "dish", "coffee", "drink", "menu"),
    "service": ("service", "staff", "waiter", "friendly", "attentive"),
    "ambience": ("ambience", "atmosphere", "decor", "beautiful", "cozy", "vibe"),
    "quiet setting": ("quiet", "calm", "peaceful", "relaxing"),
    "work setup": ("wifi", "wi-fi", "laptop", "socket", "work", "charging"),
}
CAUTION_TOPICS = {
    "slow service": ("slow", "waited", "waiting", "delay"),
    "noise": ("noisy", "loud", "noise"),
    "crowds": ("crowded", "busy", "packed"),
    "price": ("expensive", "pricey", "overpriced"),
    "parking": ("parking", "parked"),
}
POSITIVE_WORDS = ("great", "good", "excellent", "amazing", "love", "friendly", "best", "nice")
NEGATIVE_WORDS = ("bad", "poor", "terrible", "disappoint", "worst", "rude", "avoid")


class GoogleReviewProvider:
    """Queries Google Places only when a server-side key has been configured."""

    def __init__(self) -> None:
        self._cache: OrderedDict[str, tuple[float, ReviewOpinion | None]] = OrderedDict()
        self._lock = Lock()

    def enrich(self, results: list[Result]) -> list[Result]:
        if not os.getenv("GOOGLE_PLACES_API_KEY"):
            return results
        enriched = []
        for index, result in enumerate(results):
            opinion = self._opinion_for(result) if index < MAX_ENRICHED_RESULTS else None
            enriched.append(result.model_copy(update={"review_opinion": opinion}))
        return enriched

    def _opinion_for(self, result: Result) -> ReviewOpinion | None:
        key = result.place_id
        with self._lock:
            cached = self._cache.get(key)
            if cached and monotonic() - cached[0] < CACHE_TTL_SECONDS:
                return cached[1]
        opinion = self._fetch(result)
        with self._lock:
            self._cache[key] = (monotonic(), opinion)
            while len(self._cache) > 256:
                self._cache.popitem(last=False)
        return opinion

    def _fetch(self, result: Result) -> ReviewOpinion | None:
        api_key = os.getenv("GOOGLE_PLACES_API_KEY")
        if not api_key:
            return None
        payload = {
            "textQuery": f"{result.name}, {result.area}, Lagos, Nigeria",
            "languageCode": "en",
            "locationBias": {
                "circle": {
                    "center": _location_from_maps_url(result.maps_url),
                    "radius": 500.0,
                }
            },
        }
        request = Request(
            PLACES_TEXT_SEARCH_URL,
            data=json.dumps(payload).encode(),
            headers={
                "Content-Type": "application/json",
                "X-Goog-Api-Key": api_key,
                "X-Goog-FieldMask": "places.displayName,places.location,places.rating,places.userRatingCount,places.reviews,places.googleMapsUri,places.reviewsUri",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=6) as response:
                places = json.loads(response.read(500_000)).get("places", [])
        except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError):
            return None
        match = _matching_place(places, result)
        if not match:
            return None
        reviews = [review.get("text", {}).get("text", "") for review in match.get("reviews", [])]
        reviews = [review.strip() for review in reviews if review and review.strip()]
        if not reviews:
            return None
        return summarize_reviews(
            reviews,
            rating=match.get("rating"),
            review_count=match.get("userRatingCount"),
            reviews_url=match.get("reviewsUri") or match.get("googleMapsUri"),
        )


def enrich_with_reviews(results: list[Result]) -> list[Result]:
    return REVIEW_PROVIDER.enrich(results)


def summarize_reviews(reviews: list[str], rating: float | None, review_count: int | None, reviews_url: str | None) -> ReviewOpinion:
    """Summarize explicit topical signals without quoting or inventing review claims."""
    text = " ".join(reviews).lower()
    praise = _topics_in(text, POSITIVE_TOPICS)
    cautions = _topics_in(text, CAUTION_TOPICS)
    positive = sum(text.count(word) for word in POSITIVE_WORDS)
    negative = sum(text.count(word) for word in NEGATIVE_WORDS)
    sample_label = "the available review sample" if len(reviews) > 1 else "the one available review"
    if praise and cautions:
        opinion = f"{sample_label.capitalize()} praises {', '.join(praise[:2])}, with some mentions of {', '.join(cautions[:2])}."
    elif praise:
        opinion = f"{sample_label.capitalize()} is positive about {', '.join(praise[:2])}."
    elif cautions:
        opinion = f"{sample_label.capitalize()} flags {', '.join(cautions[:2])}; check recent reviews before going."
    elif rating is not None and rating >= 4 and positive >= negative:
        opinion = f"{sample_label.capitalize()} is broadly positive, though it does not point to a consistent standout detail."
    elif rating is not None and rating < 3.5:
        opinion = f"{sample_label.capitalize()} is mixed; read the recent reviews before making the trip."
    else:
        opinion = f"{sample_label.capitalize()} is mixed and does not provide a clear consensus yet."
    return ReviewOpinion(
        source="Google reviews",
        rating=rating if isinstance(rating, (int, float)) else None,
        review_count=review_count if isinstance(review_count, int) else None,
        sample_size=len(reviews),
        opinion=opinion,
        praise=praise[:3],
        cautions=cautions[:3],
        reviews_url=reviews_url if isinstance(reviews_url, str) and reviews_url.startswith("https://") else None,
    )


def _topics_in(text: str, topics: dict[str, tuple[str, ...]]) -> list[str]:
    return [label for label, terms in topics.items() if any(re.search(rf"\b{re.escape(term)}", text) for term in terms)]


def _location_from_maps_url(url: str) -> dict[str, float]:
    match = re.search(r"query=([-\d.]+)%2C([-\d.]+)", url)
    if not match:
        return {"latitude": 6.5244, "longitude": 3.3792}
    return {"latitude": float(match.group(1)), "longitude": float(match.group(2))}


def _matching_place(places: list[dict], result: Result) -> dict | None:
    expected = _normalise_name(result.name)
    for place in places:
        name = _normalise_name(place.get("displayName", {}).get("text", ""))
        if name and (name == expected or name in expected or expected in name):
            return place
    return None


def _normalise_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


REVIEW_PROVIDER = GoogleReviewProvider()
