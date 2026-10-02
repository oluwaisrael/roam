from app.models import Activity, DecisionInsight, Intent, Result


def explain_decision(intent: Intent, results: list[Result]) -> DecisionInsight:
    if not results:
        return DecisionInsight(
            headline="Roam needs more signal",
            summary="I could not find enough places that match this request yet.",
            confidence="low",
            primary_tradeoff="No scored places were available.",
            next_best_action="Try widening the area or using a simpler request.",
            caveats=["Live place coverage can be sparse depending on the area."],
        )

    best = results[0]
    second = results[1] if len(results) > 1 else None
    confidence = _confidence(best, second)
    activity_label = _activity_label(intent.activity)
    reason = _summary_reason(best)
    tradeoff = _first_real_tradeoff(best)

    understood = f" I understood this as: {intent.interpretation}." if intent.interpretation else ""
    summary = f"{best.name} is the strongest fit for {activity_label} because {reason}.{understood}"
    if second:
        gap = best.score - second.score
        if gap <= 6:
            summary += f" {second.name} is close behind, so this is a preference call rather than an obvious winner."
        elif gap >= 15:
            summary += f" It has a clear lead over {second.name}."

    caveats = _caveats(results)

    return DecisionInsight(
        headline=f"Best fit: {best.name}",
        summary=summary,
        confidence=confidence,
        primary_tradeoff=tradeoff,
        next_best_action=_next_best_action(intent, best),
        caveats=caveats,
    )


def _confidence(best: Result, second: Result | None) -> str:
    if best.data_source != "seed" and "details limited" in best.tags:
        return "medium"
    if not second:
        return "medium" if best.score >= 70 else "low"
    gap = best.score - second.score
    if best.score >= 80 and gap >= 10:
        return "high"
    if best.score >= 60:
        return "medium"
    return "low"


def _activity_label(activity: Activity) -> str:
    labels = {
        Activity.work: "working",
        Activity.date: "a date",
        Activity.quick_stop: "a quick stop",
        Activity.read: "reading",
        Activity.eat: "food",
        Activity.unwind: "unwinding",
        Activity.general: "this request",
    }
    return labels[activity]


def _first_real_tradeoff(result: Result) -> str:
    for tradeoff in result.tradeoffs:
        if tradeoff != "No major tradeoff for this request":
            return tradeoff
    return "No major tradeoff stands out from the available data."


def _summary_reason(result: Result) -> str:
    for reason in result.match_reasons:
        if reason != "Balanced fit across your request":
            return reason.lower()
    if result.travel_minutes is not None:
        return f"it best balances category fit and proximity at about {result.travel_minutes} minutes away"
    return "it best balances the available signals"


def _next_best_action(intent: Intent, best: Result) -> str:
    if best.photo_page_url:
        return "Open the picture/source link to visually confirm the place before going."
    if intent.max_minutes is None and best.travel_minutes and best.travel_minutes > 25:
        return "Try adding a travel-time limit if distance matters."
    if "details limited" in best.tags:
        return "Confirm details like Wi-Fi, power, and opening hours before you leave."
    return "Compare the top two options and choose based on the tradeoff that matters most."


def _caveats(results: list[Result]) -> list[str]:
    caveats: list[str] = []
    if any("details limited" in result.tags for result in results):
        caveats.append("Some live results come from OpenStreetMap, where Wi-Fi, noise, price, and ambience are often inferred.")
    if not any(result.photo_url for result in results):
        caveats.append("No verified place photos were found in the current live data.")
    if any(result.data_source == "seed" for result in results):
        caveats.append("Some fallback places may be seeded demo data rather than live provider results.")
    return caveats[:3]
