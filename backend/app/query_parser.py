import re

from app.models import Activity, Intent


NAIRA_PATTERN = re.compile(r"(?:₦|ngn\s*)?\s*(\d+(?:\.\d+)?)\s*(k|000)?", re.IGNORECASE)


def parse_query(query: str) -> Intent:
    text = query.lower()
    intent = Intent(raw_terms=_significant_terms(text))

    if any(word in text for word in ["work", "code", "laptop", "cowork", "wi-fi", "wifi", "power"]):
        intent.activity = Activity.work
    elif any(word in text for word in ["date", "romantic", "take someone", "dinner tonight"]):
        intent.activity = Activity.date
    elif any(word in text for word in ["read", "study", "library", "peaceful"]):
        intent.activity = Activity.read
    elif any(word in text for word in ["eat", "food", "restaurant", "brunch", "dinner", "lunch"]):
        intent.activity = Activity.eat
    elif any(word in text for word in ["quick", "closest", "nearby", "coffee near"]):
        intent.activity = Activity.quick_stop
    elif any(word in text for word in ["unwind", "lounge", "drink", "music"]):
        intent.activity = Activity.unwind

    intent.quiet = any(word in text for word in ["quiet", "peaceful", "calm", "focus", "read"])
    intent.wifi = any(word in text for word in ["wifi", "wi-fi", "internet"])
    intent.power = any(word in text for word in ["power", "charging", "socket", "outlet"])
    intent.open_now = "open now" in text or "tonight" in text
    intent.romantic = any(word in text for word in ["romantic", "date", "take someone"])
    intent.cheap = any(word in text for word in ["cheap", "affordable", "budget"])

    budget = _parse_budget(text)
    if budget:
        intent.budget_max = budget

    duration = re.search(r"(\d+(?:\.\d+)?)\s*(?:hours|hour|hrs|hr|h)\b", text)
    if duration:
        intent.duration_hours = float(duration.group(1))

    minutes = re.search(r"(?:within|under|max(?:imum)?)\s*(\d+)\s*(?:minutes|min|mins)", text)
    if minutes:
        intent.max_minutes = int(minutes.group(1))

    if intent.activity == Activity.work:
        intent.wifi = intent.wifi or "cafe" in text or "café" in text
        intent.power = intent.power or intent.duration_hours is not None and intent.duration_hours >= 3
        intent.quiet = intent.quiet or intent.duration_hours is not None and intent.duration_hours >= 2

    return intent


def _parse_budget(text: str) -> int | None:
    budget_context = re.search(r"(?:under|below|less than|max|maximum|budget(?: of)?|₦|ngn)\s*([\d.]+)\s*(k|000)?", text)
    if not budget_context:
        return None

    amount = float(budget_context.group(1))
    suffix = budget_context.group(2)
    if suffix == "k" or amount < 1000:
        amount *= 1000
    return int(amount)


def _significant_terms(text: str) -> list[str]:
    terms = []
    for term in ["quiet", "wifi", "wi-fi", "power", "date", "work", "read", "cheap", "open now", "romantic"]:
        if term in text:
            terms.append(term.replace("wi-fi", "wifi"))
    return sorted(set(terms))
