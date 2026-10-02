from app.models import Activity, Location
from app.providers import _place_from_element
from app.query_parser import parse_query
from app.scoring import score_places
from app.seed_data import PLACES


def test_parse_work_query_extracts_constraints():
    intent = parse_query("quiet cafe to work for 4 hours under ₦10k with wifi and power")

    assert intent.activity == Activity.work
    assert intent.quiet is True
    assert intent.wifi is True
    assert intent.power is True
    assert intent.budget_max == 10000
    assert intent.duration_hours == 4


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
