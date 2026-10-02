import re

from app.models import Activity, Intent


AREA_ALIASES = {
    "lekki phase 1": "Lekki Phase 1",
    "lekki": "Lekki",
    "victoria island": "Victoria Island",
    "vi": "Victoria Island",
    "ikoyi": "Ikoyi",
    "yaba": "Yaba",
    "surulere": "Surulere",
    "ikeja": "Ikeja",
    "lagos island": "Lagos Island",
    "marina": "Marina",
    "ajah": "Ajah",
}

PLACE_TYPE_KEYWORDS = {
    "cafe": {"cafe", "café", "coffee", "coffee shop"},
    "restaurant": {"restaurant", "food", "dinner", "lunch", "brunch"},
    "coworking": {"coworking", "co-working", "workspace", "workstation"},
    "library": {"library", "study"},
    "park": {"park", "outdoor"},
    "bar": {"bar", "lounge", "drinks", "cocktails"},
}

REQUIREMENT_KEYWORDS = {
    "quiet": {"quiet", "peaceful", "calm", "not noisy", "focus", "read"},
    "wifi": {"wifi", "wi-fi", "internet"},
    "power": {"power", "charging", "socket", "outlet", "plug"},
    "open_now": {"open now", "tonight", "right now"},
    "romantic": {"romantic", "date", "take someone", "intimate"},
    "cheap": {"cheap", "affordable", "budget", "low cost"},
    "parking": {"parking", "park my car"},
}

PRIORITY_KEYWORDS = {
    "distance": {"closest", "nearby", "near me", "distance matters", "within"},
    "budget": {"cheap", "affordable", "under", "below", "budget"},
    "quiet": {"quietest", "very quiet", "noise matters", "peaceful"},
    "wifi": {"reliable wifi", "strong wifi", "good wifi", "internet matters"},
    "ambience": {"nice", "romantic", "ambience", "beautiful", "cozy"},
    "food": {"good food", "food matters", "great food"},
}

NEGATIVE_KEYWORDS = {
    "noise": {"not noisy", "not loud", "avoid noise", "without noise", "no noise"},
    "crowd": {"not crowded", "avoid crowd", "not busy", "without crowd"},
    "far": {"not far", "avoid far", "too far"},
    "expensive": {"not expensive", "avoid expensive", "nothing pricey"},
}


def parse_query(query: str) -> Intent:
    text = _normalize(query)
    place_types = _extract_place_types(text)
    requirements = _extract_requirements(text)
    avoid = _extract_avoid(text)
    priority = _extract_priority(text)

    intent = Intent(
        activity=_infer_activity(text, place_types, requirements),
        place_types=place_types,
        area=_extract_area(text),
        raw_terms=_significant_terms(text, place_types, requirements),
        must_have=requirements,
        avoid=avoid,
        priority=priority,
    )

    intent.quiet = "quiet" in requirements or "noise" in avoid
    intent.wifi = "wifi" in requirements
    intent.power = "power" in requirements
    intent.open_now = "open_now" in requirements
    intent.romantic = "romantic" in requirements
    intent.cheap = "cheap" in requirements

    budget = _parse_budget(text)
    if budget:
        intent.budget_max = budget

    duration = re.search(r"(\d+(?:\.\d+)?)\s*(?:hours|hour|hrs|hr|h)\b", text)
    if duration:
        intent.duration_hours = float(duration.group(1))

    minutes = re.search(r"(?:within|under|max(?:imum)?|less than)\s*(\d+)\s*(?:minutes|min|mins)", text)
    if minutes:
        intent.max_minutes = int(minutes.group(1))

    if intent.activity == Activity.work:
        intent.wifi = intent.wifi or "cafe" in place_types or "coworking" in place_types
        intent.power = intent.power or intent.duration_hours is not None and intent.duration_hours >= 3
        intent.quiet = intent.quiet or intent.duration_hours is not None and intent.duration_hours >= 2
        _append_unique(intent.must_have, ["wifi"] if intent.wifi else [])
        _append_unique(intent.must_have, ["power"] if intent.power else [])
        _append_unique(intent.must_have, ["quiet"] if intent.quiet else [])

    intent.interpretation = _interpretation(intent)
    return intent


def _normalize(query: str) -> str:
    return re.sub(r"\s+", " ", query.lower()).strip()


def _infer_activity(text: str, place_types: list[str], requirements: list[str]) -> Activity:
    if any(word in text for word in ["work", "code", "laptop", "cowork", "co-working", "workspace"]):
        return Activity.work
    if "romantic" in requirements or any(word in text for word in ["date", "take someone"]):
        return Activity.date
    if any(word in text for word in ["read", "study", "library", "book"]):
        return Activity.read
    if any(word in text for word in ["eat", "food", "restaurant", "brunch", "dinner", "lunch"]):
        return Activity.eat
    if any(word in text for word in ["quick", "closest", "nearby", "coffee", "cafe", "café"]):
        return Activity.quick_stop
    if any(word in text for word in ["unwind", "lounge", "drink", "music", "bar"]):
        return Activity.unwind
    if "cafe" in place_types:
        return Activity.quick_stop
    return Activity.general


def _extract_place_types(text: str) -> list[str]:
    place_types = []
    for place_type, keywords in PLACE_TYPE_KEYWORDS.items():
        if any(keyword in text for keyword in keywords):
            place_types.append(place_type)
    return place_types


def _extract_area(text: str) -> str | None:
    for alias, area in sorted(AREA_ALIASES.items(), key=lambda item: len(item[0]), reverse=True):
        if re.search(rf"\b{re.escape(alias)}\b", text):
            return area
    return None


def _extract_requirements(text: str) -> list[str]:
    requirements = []
    for requirement, keywords in REQUIREMENT_KEYWORDS.items():
        if any(keyword in text for keyword in keywords):
            requirements.append(requirement)
    return requirements


def _extract_priority(text: str) -> list[str]:
    priority = []
    for signal, keywords in PRIORITY_KEYWORDS.items():
        if any(keyword in text for keyword in keywords):
            priority.append(signal)
    return priority


def _extract_avoid(text: str) -> list[str]:
    avoid = []
    for signal, keywords in NEGATIVE_KEYWORDS.items():
        if any(keyword in text for keyword in keywords):
            avoid.append(signal)
    return avoid


def _parse_budget(text: str) -> int | None:
    budget_context = re.search(r"(?:under|below|less than|max|maximum|budget(?: of)?|₦|ngn)\s*([\d.]+)\s*(k|000)?", text)
    if not budget_context:
        return None

    amount = float(budget_context.group(1))
    suffix = budget_context.group(2)
    if suffix == "k" or amount < 1000:
        amount *= 1000
    return int(amount)


def _significant_terms(text: str, place_types: list[str], requirements: list[str]) -> list[str]:
    terms = set(place_types + requirements)
    for term in ["date", "work", "read", "open now", "restaurant", "coffee", "near me"]:
        if term in text:
            terms.add(term.replace("coffee", "cafe"))
    return sorted(terms)


def _interpretation(intent: Intent) -> str:
    pieces = [intent.activity.value.replace("_", " ")]
    if intent.place_types:
        pieces.append(" or ".join(intent.place_types))
    if intent.area:
        pieces.append(f"around {intent.area}")
    if intent.budget_max:
        pieces.append(f"under ₦{intent.budget_max:,}")
    if intent.max_minutes:
        pieces.append(f"within {intent.max_minutes} minutes")
    if intent.must_have:
        pieces.append("must have " + ", ".join(item.replace("_", " ") for item in intent.must_have))
    if intent.avoid:
        pieces.append("avoid " + ", ".join(intent.avoid))
    if intent.priority:
        pieces.append("prioritize " + ", ".join(intent.priority))
    return "; ".join(pieces)


def _append_unique(items: list[str], additions: list[str]) -> None:
    for addition in additions:
        if addition not in items:
            items.append(addition)
