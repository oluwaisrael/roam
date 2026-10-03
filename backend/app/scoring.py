from datetime import datetime
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from app.models import Activity, Evidence, Intent, Location, Place, Result, distance_km


BASE_WEIGHTS: dict[Activity, dict[str, float]] = {
    Activity.work: {"quietness": 1.4, "wifi": 1.5, "power": 1.3, "seating": 1.0, "distance": 0.8, "budget": 0.8, "quality": 0.5},
    Activity.date: {"ambience": 1.5, "food": 1.0, "date": 1.4, "distance": 0.7, "budget": 0.9, "quality": 0.7},
    Activity.quick_stop: {"distance": 1.8, "open": 1.2, "budget": 0.9, "quality": 0.4, "category": 3.5},
    Activity.read: {"quietness": 1.7, "seating": 1.0, "budget": 0.8, "distance": 0.8, "quality": 0.4},
    Activity.eat: {"food": 1.5, "ambience": 0.8, "budget": 0.9, "distance": 0.7, "quality": 0.8},
    Activity.unwind: {"ambience": 1.3, "food": 0.6, "distance": 0.7, "quality": 0.7, "open": 0.8},
    Activity.general: {"distance": 1.0, "budget": 0.8, "quality": 0.8, "ambience": 0.5},
}


def score_places(places: list[Place], intent: Intent, origin: Location | None = None, at_hour: int | None = None) -> list[Result]:
    results = [_score_place(place, intent, origin, at_hour) for place in places]
    return sorted(results, key=lambda result: result.score, reverse=True)


def _score_place(place: Place, intent: Intent, origin: Location | None, at_hour: int | None = None) -> Result:
    weights = BASE_WEIGHTS[intent.activity].copy()
    if intent.quiet:
        weights["quietness"] = weights.get("quietness", 0) + 1.2
    if intent.wifi:
        weights["wifi"] = weights.get("wifi", 0) + 1.4
    if intent.power:
        weights["power"] = weights.get("power", 0) + 1.1
    if intent.romantic:
        weights["date"] = weights.get("date", 0) + 1.2
        weights["ambience"] = weights.get("ambience", 0) + 0.8
    if intent.open_now:
        weights["open"] = weights.get("open", 0) + 1.0
    for priority in intent.priority:
        if priority == "distance":
            weights["distance"] = weights.get("distance", 0) + 1.0
        elif priority == "budget":
            weights["budget"] = weights.get("budget", 0) + 1.0
        elif priority == "quiet":
            weights["quietness"] = weights.get("quietness", 0) + 1.0
        elif priority == "wifi":
            weights["wifi"] = weights.get("wifi", 0) + 1.0
        elif priority == "ambience":
            weights["ambience"] = weights.get("ambience", 0) + 1.0
        elif priority == "food":
            weights["food"] = weights.get("food", 0) + 1.0

    distance = distance_km(origin, place.location) if origin else None
    travel_minutes = round(distance / 24 * 60) if distance is not None else None
    live = place.data_source != "seed"
    if live and "open-24h" not in place.tags and "hours-listed" not in place.tags:
        open_now = None
    else:
        open_now = _is_open_now(place, at_hour)

    components = {
        "quietness": place.quietness / 5,
        "wifi": place.wifi / 5,
        "power": place.power / 5,
        "seating": place.seating / 5,
        "ambience": place.ambience / 5,
        "food": place.food / 5,
        "date": place.date_friendly / 5,
        "quality": place.rating / 5,
        "open": 0.5 if open_now is None else int(open_now),
        "budget": _budget_fit(place, intent),
        "distance": _distance_fit(travel_minutes, intent),
        "category": _category_fit(place, intent),
    }

    weighted = sum(components[key] * weight for key, weight in weights.items())
    max_score = sum(weights.values())
    score = round((weighted / max_score) * 100)
    if intent.budget_max and place.typical_spend > intent.budget_max:
        overage = (place.typical_spend - intent.budget_max) / max(intent.budget_max, 1)
        score -= round(min(28, overage * 40))
    if "noise" in intent.avoid and place.quietness <= 2:
        score -= 18
    if "crowd" in intent.avoid and place.category in {"Bar", "Quick food"}:
        score -= 10
    if "far" in intent.avoid and travel_minutes is not None and travel_minutes > (intent.max_minutes or 20):
        score -= 14
    if "expensive" in intent.avoid and place.price_level >= 3:
        score -= 12
    score = max(0, min(100, score))

    reasons = _match_reasons(place, intent, travel_minutes, open_now)
    tradeoffs = _tradeoffs(place, intent, travel_minutes, open_now)
    if live:
        reasons = [f"{place.category} matches your plans"]
        if intent.budget_max is not None and place.typical_spend <= intent.budget_max:
            reasons.append("Estimated spend fits your budget")
        if intent.wifi and "wifi" in place.tags:
            reasons.append("Wi-Fi listed on OpenStreetMap")
        if distance is not None:
            reasons.append(f"{distance:.1f} km straight-line distance")
        tradeoffs = ["Prices, noise and amenities need confirmation"] + [item for item in tradeoffs if "budget" in item or "away" in item]
        if intent.open_now and open_now is None:
            tradeoffs.insert(0, "Current opening hours are unverified")
    maps_url = "https://www.google.com/maps/search/?" + urlencode({"api": 1, "query": f"{place.location.lat},{place.location.lng}"})
    photos_url = "https://www.google.com/search?" + urlencode({"tbm": "isch", "q": f"{place.name} {place.area} Lagos"})
    evidence = [
        Evidence(label="Budget", value=f"NGN {place.typical_spend:,} / person", status="estimated" if live else "demo"),
        Evidence(label="Wi-Fi", value="Listed by the map contributor" if "wifi" in place.tags else "Not confirmed", status="listed" if "wifi" in place.tags else "unknown"),
        Evidence(label="Quiet", value="Not confirmed", status="unknown"),
        Evidence(label="Power", value="Not confirmed", status="unknown"),
        Evidence(label="Hours", value=_hours_evidence(place), status="listed" if {"open-24h", "hours-listed"} & set(place.tags) else "unknown"),
    ]

    return Result(
        place_id=place.id,
        name=place.name,
        category=place.category,
        area=place.area,
        score=score,
        rating=None if live else place.rating,
        price_level=place.price_level,
        typical_spend=place.typical_spend,
        distance_km=round(distance, 1) if distance is not None else None,
        travel_minutes=travel_minutes,
        open_now=open_now,
        match_reasons=reasons[:4],
        tradeoffs=tradeoffs[:3],
        tags=place.tags,
        data_source=place.data_source,
        photo_url=place.photo_url,
        photo_page_url=place.photo_page_url,
        maps_url=maps_url,
        photos_url=place.photo_page_url or photos_url,
        evidence=evidence,
    )


def _budget_fit(place: Place, intent: Intent) -> float:
    if intent.budget_max is None:
        return 0.75 if place.price_level <= 3 else 0.45
    if place.typical_spend <= intent.budget_max:
        return 1
    overage = (place.typical_spend - intent.budget_max) / max(intent.budget_max, 1)
    return max(0, 1 - overage * 1.6)


def _distance_fit(minutes: int | None, intent: Intent) -> float:
    if minutes is None:
        return 0.7
    target = intent.max_minutes or 20
    if minutes <= target:
        return 1
    return max(0, 1 - (minutes - target) / target)


def _category_fit(place: Place, intent: Intent) -> float:
    terms = set(intent.raw_terms)
    category = _normalized_category(place.category)
    if {"cafe", "coffee"} & terms:
        if category == "cafe":
            return 1
        if category in {"quick food", "restaurant"}:
            return 0.35
        return 0
    if "restaurant" in terms:
        if category == "restaurant":
            return 1
        if category in {"cafe", "quick food"}:
            return 0.35
        return 0
    return 0.7


def _is_open_now(place: Place, at_hour: int | None = None) -> bool:
    hour = datetime.now(ZoneInfo("Africa/Lagos")).hour if at_hour is None else at_hour
    if place.closes_at < place.opens_at:
        return hour >= place.opens_at or hour < place.closes_at
    if place.closes_at == 24:
        return place.opens_at <= hour <= 23
    return place.opens_at <= hour < place.closes_at


def _normalized_category(category: str) -> str:
    aliases = {
        "coffee": "cafe",
        "lounge": "bar",
        "culture": "restaurant",
    }
    normalized = category.strip().lower()
    return aliases.get(normalized, normalized)


def _hours_evidence(place: Place) -> str:
    if "open-24h" in place.tags:
        return "Listed as 24/7"
    if "hours-listed" in place.tags:
        return f"Listed around {place.opens_at}:00-{place.closes_at}:00"
    return "Confirm before going"


def _match_reasons(place: Place, intent: Intent, travel_minutes: int | None, open_now: bool) -> list[str]:
    reasons: list[str] = []
    if intent.budget_max and place.typical_spend <= intent.budget_max:
        reasons.append("Within your budget")
    if intent.quiet and place.quietness >= 4:
        reasons.append("Quiet enough for focus")
    if intent.wifi and place.wifi >= 4:
        reasons.append("Strong Wi-Fi")
    if intent.power and place.power >= 4:
        reasons.append("Reliable power access")
    if intent.romantic and place.date_friendly >= 4:
        reasons.append("Strong date-night ambience")
    if intent.activity == Activity.work and place.work_friendly >= 4:
        reasons.append("Comfortable for a long work session")
    if intent.activity == Activity.eat and place.food >= 4:
        reasons.append("Food is a strong reason to go")
    if travel_minutes is not None and travel_minutes <= (intent.max_minutes or 20):
        reasons.append(f"{travel_minutes} min away")
    if intent.open_now and open_now:
        reasons.append("Open now")
    if not reasons:
        reasons.append("Balanced fit across your request")
    return reasons


def _tradeoffs(place: Place, intent: Intent, travel_minutes: int | None, open_now: bool) -> list[str]:
    tradeoffs: list[str] = []
    if intent.budget_max and place.typical_spend > intent.budget_max:
        tradeoffs.append(f"About ₦{place.typical_spend - intent.budget_max:,} above budget")
    if intent.quiet and place.quietness <= 2:
        tradeoffs.append("Likely too lively for quiet focus")
    elif intent.quiet and place.quietness == 3:
        tradeoffs.append("Can get moderately busy")
    if intent.wifi and place.wifi <= 2:
        tradeoffs.append("Wi-Fi is not a strength")
    if intent.power and place.power <= 2:
        tradeoffs.append("Power access may be limited")
    if travel_minutes is not None and intent.max_minutes and travel_minutes > intent.max_minutes:
        tradeoffs.append(f"{travel_minutes} min away, beyond your target")
    elif "far" in intent.avoid and travel_minutes is not None and travel_minutes > 20:
        tradeoffs.append(f"{travel_minutes} min away, which may feel far")
    if intent.open_now and not open_now:
        tradeoffs.append("Not open right now")
    if "expensive" in intent.avoid and place.price_level >= 3:
        tradeoffs.append("May feel pricey for this request")
    if not tradeoffs:
        tradeoffs.append("No major tradeoff for this request")
    return tradeoffs
