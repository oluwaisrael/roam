import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app import main
from app.intelligence import explain_decision
from app.main import PHOTO_MEMORY, SEARCH_MEMORY, SearchContext, _remember
from app.models import Activity, Location, RefineRequest, SearchRequest
from app.providers import CompositePlaceProvider, PlaceProvider, SeedPlaceProvider, _photo_page_url, _photo_url, _place_from_element, _search_origin
from app.query_parser import parse_followup, parse_query
from app.reviews import summarize_reviews
from app.scoring import local_distance_limit_km, score_places
from app.seed_data import PLACES
from app.understanding import understand


class BrokenProvider(PlaceProvider):
    def search(self, intent, location):
        raise RuntimeError("provider failed")


class StaticProvider(PlaceProvider):
    def search(self, intent, location):
        return PLACES


def test_parse_work_query_extracts_constraints():
    intent = parse_query("quiet cafe to work for 4 hours under ₦10k with wifi and power")

    assert intent.activity == Activity.work
    assert intent.quiet is True
    assert intent.wifi is True
    assert intent.power is True
    assert intent.budget_max == 10000
    assert intent.duration_hours == 4
    assert intent.place_types == ["cafe"]
    assert "wifi" in intent.must_have
    assert "power" in intent.must_have


def test_requests_strip_text_and_reject_empty_refine():
    assert SearchRequest(query="  quiet cafe  ").query == "quiet cafe"
    assert RefineRequest(search_id="  abc  ", query="  closer  ").search_id == "abc"
    with pytest.raises(ValidationError):
        RefineRequest(search_id="abc")


def test_parse_budget_handles_suffix_and_commas():
    assert parse_query("cafe with 10k budget").budget_max == 10000
    assert parse_query("dinner ₦10,500 max").budget_max == 10500
    assert parse_query("restaurant within 10 minutes").budget_max is None


def test_parse_prompt_understands_area_avoid_and_priority():
    intent = parse_query("date spot around Lekki under ₦30k, not noisy, distance matters more")

    assert intent.activity == Activity.date
    assert intent.area == "Lekki"
    assert intent.budget_max == 30000
    assert "noise" in intent.avoid
    assert "distance" in intent.priority
    assert "restaurant" in intent.place_types or "bar" in intent.place_types or intent.romantic is True
    assert "around Lekki" in intent.interpretation


def test_tonight_does_not_mean_open_now():
    intent = parse_query("romantic date spot tonight around VI")

    assert intent.activity == Activity.date
    assert intent.romantic is True
    assert intent.open_now is False


def test_followup_can_remove_budget_without_losing_context():
    previous = parse_query("quiet cafe in Yaba under ₦10k with wifi")
    intent = parse_followup("remove budget", previous)

    assert intent.area == "Yaba"
    assert intent.budget_max is None
    assert "budget" not in intent.priority
    assert intent.wifi is True


def test_followup_can_turn_off_previous_requirement():
    previous = parse_query("quiet cafe with wifi and power")
    intent = parse_followup("wifi does not matter", previous)

    assert intent.wifi is False
    assert intent.power is True
    assert "wifi" not in intent.must_have


def test_rules_understanding_can_ask_for_clarification(monkeypatch):
    monkeypatch.setenv("ROAM_AI_PROVIDER", "rules")

    _, engine, _, clarification = understand("vegan dinner around Lekki")

    assert engine == "rules"
    assert clarification is not None
    assert "confirm" in clarification.lower()


def test_named_area_changes_provider_search_origin():
    intent = parse_query("date spot around Lekki under ₦30k")
    origin = _search_origin(intent, Location(lat=6.52, lng=3.37))

    assert round(origin.lat, 3) == 6.470
    assert round(origin.lng, 3) == 3.585


def test_composite_provider_falls_back_when_enabled(monkeypatch):
    monkeypatch.setenv("ROAM_DEMO_DATA", "true")
    provider = CompositePlaceProvider([BrokenProvider()], SeedPlaceProvider())
    places = provider.search(parse_query("quiet cafe in Yaba"), None)

    assert places
    assert places[0].data_source == "seed"


def test_search_memory_is_bounded(monkeypatch):
    monkeypatch.setattr("app.main.MAX_MEMORY_ITEMS", 2)
    SEARCH_MEMORY.clear()
    PHOTO_MEMORY.clear()
    intent = parse_query("quiet cafe")

    for index in range(3):
        _remember(f"search-{index}", SearchContext(query="quiet cafe", intent=intent, location=None), {})

    assert list(SEARCH_MEMORY) == ["search-1", "search-2"]
    assert len(PHOTO_MEMORY) <= 2


def test_search_endpoint_returns_decision_metadata(monkeypatch):
    monkeypatch.setattr(main, "PLACE_PROVIDER", StaticProvider())
    client = TestClient(main.app)

    response = client.post("/api/search", json={"query": "quiet cafe in Yaba under ₦10k"})

    assert response.status_code == 200
    body = response.json()
    assert body["engine"] in {"ai", "rules"}
    assert body["data_status"] == "demo"
    assert body["suggestions"]
    assert body["results"][0]["evidence"]


def test_health_endpoint_exposes_safe_runtime_status(monkeypatch):
    monkeypatch.setenv("ROAM_AI_PROVIDER", "rules")
    client = TestClient(main.app)

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "version": "0.1.0",
        "ai_provider": "rules",
        "demo_data": "false",
    }


def test_refine_endpoint_accepts_followup_query(monkeypatch):
    monkeypatch.setattr(main, "PLACE_PROVIDER", StaticProvider())
    client = TestClient(main.app)
    search = client.post("/api/search", json={"query": "quiet cafe with wifi"}).json()

    response = client.post("/api/search/refine", json={"search_id": search["search_id"], "query": "closer and no wifi"})

    assert response.status_code == 200
    body = response.json()
    assert body["intent"]["wifi"] is False
    assert body["intent"]["max_minutes"] == 15


def test_work_query_prefers_work_friendly_places():
    intent = parse_query("quiet place to work under ₦10000 with wifi and power")
    results = score_places(PLACES, intent, Location(lat=6.52, lng=3.37))

    assert results[0].name in {"Cafe One Yaba", "Cafe Neo Victoria Island", "MyYa's Cafe"}
    assert "Strong Wi-Fi" in results[0].match_reasons or "Reliable power access" in results[0].match_reasons


def test_current_location_excludes_places_beyond_local_radius():
    intent = parse_query("quiet cafe to work")
    origin = Location(lat=6.52, lng=3.37)
    nearby = PLACES[0].model_copy(update={"location": Location(lat=6.525, lng=3.375)})
    far_away = PLACES[1].model_copy(update={"location": Location(lat=6.65, lng=3.37)})

    results = score_places([nearby, far_away], intent, origin)

    assert local_distance_limit_km(intent, origin) == 7.0
    assert [result.place_id for result in results] == [nearby.id]


def test_explicit_travel_time_sets_a_stricter_local_radius():
    intent = parse_query("cafe near me within 10 minutes")

    assert local_distance_limit_km(intent, Location(lat=6.52, lng=3.37)) == 3.3


def test_review_opinion_uses_only_signals_found_in_review_text():
    opinion = summarize_reviews(
        [
            "The staff were friendly and the coffee was excellent. Quiet place to work.",
            "Great ambience, but service was slow when it got busy.",
        ],
        rating=4.3,
        review_count=120,
        reviews_url="https://www.google.com/maps",
    )

    assert opinion.source == "Google reviews"
    assert opinion.sample_size == 2
    assert "service" in opinion.praise
    assert "slow service" in opinion.cautions
    assert "parking" not in opinion.cautions
    assert "praises" in opinion.opinion


def test_date_query_surfaces_ambience_and_tradeoffs():
    intent = parse_query("romantic date spot tonight under ₦30000")
    results = score_places(PLACES, intent, Location(lat=6.43, lng=3.42))

    assert any(result.name in {"Art Cafe", "The Bistro", "Yellow Chilli"} for result in results[:3])
    assert results[0].match_reasons
    assert results[0].tradeoffs


def test_live_listed_hours_can_satisfy_open_now():
    place = _place_from_element(
        {
            "type": "node",
            "id": 125,
            "lat": 6.45,
            "lon": 3.39,
            "tags": {"name": "Listed Hours Cafe", "amenity": "cafe", "opening_hours": "08:00-22:00"},
        }
    )
    intent = parse_query("cafe open now")
    result = score_places([place], intent, at_hour=12)[0]

    assert result.open_now is True
    assert any(item.label == "Hours" and item.status == "listed" for item in result.evidence)


def test_osm_element_normalizes_to_place():
    place = _place_from_element(
        {
            "type": "node",
            "id": 123,
            "lat": 6.45,
            "lon": 3.39,
            "tags": {
                "name": "Real Cafe",
                "amenity": "cafe",
                "internet_access": "wlan",
                "addr:suburb": "Ikoyi",
            },
        }
    )

    assert place is not None
    assert place.name == "Real Cafe"
    assert place.category == "Cafe"
    assert place.area == "Ikoyi"
    assert place.wifi == 4
    assert place.data_source == "OpenStreetMap"


def test_osm_element_uses_simple_opening_hours():
    place = _place_from_element(
        {
            "type": "node",
            "id": 124,
            "lat": 6.45,
            "lon": 3.39,
            "tags": {"name": "Evening Cafe", "amenity": "cafe", "opening_hours": "Mo-Su 08:00-22:00"},
        }
    )
    assert place is not None
    assert place.opens_at == 8
    assert place.closes_at == 22
    assert "hours-listed" in place.tags


def test_commons_photo_paths_are_extracted():
    tags = {"wikimedia_commons": "File:Example cafe.jpg"}

    assert _photo_url(tags) == "https://commons.wikimedia.org/wiki/Special:FilePath/Example%20cafe.jpg"
    assert _photo_page_url(tags) == "https://commons.wikimedia.org/wiki/File:Example_cafe.jpg"


def test_intelligence_explains_top_result():
    intent = parse_query("quiet place to work under ₦10000 with wifi and power")
    results = score_places(PLACES, intent, Location(lat=6.52, lng=3.37))[:3]
    insight = explain_decision(intent, results)

    assert results[0].name in insight.headline
    assert insight.confidence in {"high", "medium", "low"}
    assert insight.summary
    assert insight.next_best_action
