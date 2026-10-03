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

    return normalize_intent(intent, text)


def normalize_intent(intent: Intent, text: str = "") -> Intent:
    text = _normalize(text).replace("’", "'")
    for key, words in REQUIREMENT_KEYWORDS.items():
        if not hasattr(intent, key):
            continue
        for word in words:
            if re.search(rf"(?:don't need|do not need|don't care about|without|no|ignore)\s+(?:the\s+)?{re.escape(word)}\b|{re.escape(word)}\s+(?:doesn't matter|does not matter|is optional|isn't necessary)", text):
                setattr(intent, key, False)
                if key in intent.priority:
                    intent.priority.remove(key)
    intent.must_have = [key for key in ("quiet", "wifi", "power", "open_now", "romantic") if getattr(intent, key)]
    if not intent.quiet:
        intent.avoid = [item for item in intent.avoid if item != "noise"]
    intent.interpretation = _interpretation(intent)
    return intent


def parse_followup(query: str, previous: Intent) -> Intent:
    parsed = parse_query(query)
    text = _normalize(query).replace("’", "'")
    changes = {}
    for key in ("area", "budget_max", "duration_hours", "max_minutes"):
        if getattr(parsed, key) is not None:
            changes[key] = getattr(parsed, key)
    if parsed.place_types:
        changes["place_types"] = parsed.place_types
    if parsed.activity != Activity.general:
        changes["activity"] = parsed.activity
    for key in ("quiet", "wifi", "power", "open_now", "romantic", "cheap"):
        if getattr(parsed, key):
            changes[key] = True
    for key in ("priority", "avoid"):
        changes[key] = list(dict.fromkeys(getattr(parsed, key) + getattr(previous, key)))
    if "cheaper" in text:
        changes["budget_max"] = max(0, round((previous.budget_max or 15000) * 0.75))
        changes["priority"] = ["budget"]
    if any(word in text for word in ("closer", "nearer", "distance matters")):
        changes["priority"] = ["distance"]
        changes["max_minutes"] = parsed.max_minutes or 15
    if any(word in text for word in ("quieter", "less noisy")):
        changes.update(quiet=True, priority=["quiet"])
    if any(word in text for word in ("no budget limit", "remove budget", "budget doesn't matter")):
        changes.update(budget_max=None, cheap=False)
        existing_priority = changes.get("priority", previous.priority)
        changes["priority"] = [item for item in existing_priority if item != "budget"]
    for key, words in REQUIREMENT_KEYWORDS.items():
        if _negates_requirement(text, words):
            changes[key] = False
    return normalize_intent(Intent.model_validate({**previous.model_dump(), **changes}), text)


def _negates_requirement(text: str, words: set[str]) -> bool:
    for word in words:
        if re.search(rf"(?:don't need|do not need|don't care about|without|no|ignore)\s+(?:the\s+)?{re.escape(word)}\b|{re.escape(word)}\s+(?:doesn't matter|does not matter|is optional|isn't necessary)", text):
            return True
    return False


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
    prefix_pattern = r"(?:₦|ngn\s*|(?:under|below|less than|max(?:imum)?|budget(?: of| to)?|spend|up to)\s*(?:₦|ngn)?\s*)(\d[\d,]*(?:\.\d+)?)\s*(k)?\b"
    suffix_pattern = r"\b(\d[\d,]*(?:\.\d+)?)\s*(k)?\s*(?:budget|max(?:imum)?|or less|and below)\b"
    for match in re.finditer(prefix_pattern, text):
        if re.match(r"\s*(?:minutes?|mins?|hours?|hrs?)\b", text[match.end():]):
            continue
        return _budget_amount(match)
    for match in re.finditer(suffix_pattern, text):
        return _budget_amount(match)
    return None


def _budget_amount(match: re.Match) -> int:
    amount = float(match.group(1).replace(",", ""))
    return min(10000000, int(amount * (1000 if match.group(2) else 1)))


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
