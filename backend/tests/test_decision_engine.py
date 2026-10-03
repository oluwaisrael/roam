from app.intelligence import explain_decision
from app.models import Activity, Location
from app.providers import CompositePlaceProvider, PlaceProvider, SeedPlaceProvider, _photo_page_url, _photo_url, _place_from_element, _search_origin
from app.query_parser import parse_query
from app.query_parser import parse_followup
from app.scoring import score_places
from app.seed_data import PLACES


class BrokenProvider(PlaceProvider):
    def search(self, intent, location):
        raise RuntimeError("provider failed")


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


def test_parse_prompt_understands_area_avoid_and_priority():
    intent = parse_query("date spot around Lekki under ₦30k, not noisy, distance matters more")

    assert intent.activity == Activity.date
    assert intent.area == "Lekki"
    assert intent.budget_max == 30000
    assert "noise" in intent.avoid
    assert "distance" in intent.priority
    assert "restaurant" in intent.place_types or "bar" in intent.place_types or intent.romantic is True
    assert "around Lekki" in intent.interpretation


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


def test_work_query_prefers_work_friendly_places():
    intent = parse_query("quiet place to work under ₦10000 with wifi and power")
    results = score_places(PLACES, intent, Location(lat=6.52, lng=3.37))

    assert results[0].name in {"Cafe One Yaba", "Cafe Neo Victoria Island", "MyYa's Cafe"}
    assert "Strong Wi-Fi" in results[0].match_reasons or "Reliable power access" in results[0].match_reasons


def test_date_query_surfaces_ambience_and_tradeoffs():
    intent = parse_query("romantic date spot tonight under ₦30000")
    results = score_places(PLACES, intent, Location(lat=6.43, lng=3.42))

    assert any(result.name in {"Art Cafe", "The Bistro", "Yellow Chilli"} for result in results[:3])
    assert results[0].match_reasons
    assert results[0].tradeoffs


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
