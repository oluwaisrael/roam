from abc import ABC, abstractmethod
import json
from urllib.error import URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from app.models import Activity, Intent, Location, Place
from app.seed_data import PLACES


DEFAULT_LAGOS_LOCATION = Location(lat=6.5244, lng=3.3792)


class PlaceProvider(ABC):
    @abstractmethod
    def search(self, intent: Intent, location: Location | None) -> list[Place]:
        """Return candidate places for the parsed user intent."""


class SeedPlaceProvider(PlaceProvider):
    def search(self, intent: Intent, location: Location | None) -> list[Place]:
        return PLACES


class OverpassPlaceProvider(PlaceProvider):
    endpoint = "https://overpass-api.de/api/interpreter"

    def search(self, intent: Intent, location: Location | None) -> list[Place]:
        origin = location or DEFAULT_LAGOS_LOCATION
        query = _build_overpass_query(intent, origin)
        payload = urlencode({"data": query}).encode()
        request = Request(
            self.endpoint,
            data=payload,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": "Roam MVP contact: https://github.com/oluwaisrael/roam",
            },
            method="POST",
        )

        try:
            with urlopen(request, timeout=8) as response:
                body = response.read().decode()
            data = json.loads(body)
        except (TimeoutError, URLError, OSError, json.JSONDecodeError):
            return []

        places = [_place_from_element(element) for element in data.get("elements", [])]
        return [place for place in places if place is not None]


class NominatimPlaceProvider(PlaceProvider):
    endpoint = "https://nominatim.openstreetmap.org/search"

    def search(self, intent: Intent, location: Location | None) -> list[Place]:
        origin = location or DEFAULT_LAGOS_LOCATION
        search_terms = _nominatim_terms(intent)
        places: list[Place] = []
        seen_ids: set[str] = set()

        for term in search_terms:
            params = {
                "q": term,
                "format": "jsonv2",
                "limit": "8",
                "addressdetails": "1",
                "extratags": "1",
                "bounded": "1",
                "viewbox": _viewbox(origin),
            }
            request = Request(
                f"{self.endpoint}?{urlencode(params)}",
                headers={
                    "Accept": "application/json",
                    "User-Agent": "Roam MVP contact: https://github.com/oluwaisrael/roam",
                },
                method="GET",
            )
            try:
                with urlopen(request, timeout=8) as response:
                    data = json.loads(response.read().decode())
            except (TimeoutError, URLError, OSError, json.JSONDecodeError):
                continue

            for item in data:
                place = _place_from_nominatim_result(item)
                if place and place.id not in seen_ids:
                    seen_ids.add(place.id)
                    places.append(place)

            if len(places) >= 6:
                break

        return places


class CompositePlaceProvider(PlaceProvider):
    def __init__(self, providers: list[PlaceProvider], fallback: PlaceProvider) -> None:
        self.providers = providers
        self.fallback = fallback

    def search(self, intent: Intent, location: Location | None) -> list[Place]:
        for provider in self.providers:
            places = provider.search(intent, location)
            if len(places) >= 3:
                return places
        return self.fallback.search(intent, location)


def _build_overpass_query(intent: Intent, origin: Location) -> str:
    radius = 6500
    if intent.max_minutes:
        radius = max(1500, min(15000, intent.max_minutes * 500))

    clauses = []
    for key, value in _osm_filters(intent):
        clauses.append(f'node["{key}"="{value}"](around:{radius},{origin.lat},{origin.lng});')
        clauses.append(f'way["{key}"="{value}"](around:{radius},{origin.lat},{origin.lng});')
        clauses.append(f'relation["{key}"="{value}"](around:{radius},{origin.lat},{origin.lng});')

    return f"""
        [out:json][timeout:8];
        (
          {"".join(clauses)}
        );
        out center tags 40;
    """


def _osm_filters(intent: Intent) -> list[tuple[str, str]]:
    if intent.activity == Activity.work:
        return [("amenity", "cafe"), ("amenity", "library"), ("office", "coworking")]
    if intent.activity == Activity.date:
        return [("amenity", "restaurant"), ("amenity", "cafe"), ("amenity", "bar")]
    if intent.activity == Activity.read:
        return [("amenity", "library"), ("amenity", "cafe"), ("leisure", "park")]
    if intent.activity == Activity.eat:
        return [("amenity", "restaurant"), ("amenity", "fast_food"), ("amenity", "cafe")]
    if intent.activity == Activity.quick_stop:
        return [("amenity", "cafe"), ("amenity", "fast_food"), ("amenity", "restaurant")]
    if intent.activity == Activity.unwind:
        return [("amenity", "bar"), ("amenity", "restaurant"), ("leisure", "park")]
    return [("amenity", "cafe"), ("amenity", "restaurant"), ("amenity", "library"), ("leisure", "park")]


def _nominatim_terms(intent: Intent) -> list[str]:
    if intent.activity == Activity.work:
        return ["cafe Lagos Nigeria", "coworking Lagos Nigeria", "library Lagos Nigeria"]
    if intent.activity == Activity.date:
        return ["restaurant Lagos Nigeria", "cafe Lagos Nigeria", "bar Lagos Nigeria"]
    if intent.activity == Activity.read:
        return ["library Lagos Nigeria", "quiet cafe Lagos Nigeria", "park Lagos Nigeria"]
    if intent.activity == Activity.eat:
        return ["restaurant Lagos Nigeria", "cafe Lagos Nigeria", "fast food Lagos Nigeria"]
    if intent.activity == Activity.quick_stop:
        return ["cafe Lagos Nigeria", "coffee Lagos Nigeria", "fast food Lagos Nigeria"]
    if intent.activity == Activity.unwind:
        return ["bar Lagos Nigeria", "park Lagos Nigeria", "restaurant Lagos Nigeria"]
    return ["cafe Lagos Nigeria", "restaurant Lagos Nigeria", "library Lagos Nigeria"]


def _viewbox(origin: Location) -> str:
    lat_delta = 0.16
    lng_delta = 0.16
    left = origin.lng - lng_delta
    right = origin.lng + lng_delta
    top = origin.lat + lat_delta
    bottom = origin.lat - lat_delta
    return f"{left},{top},{right},{bottom}"


def _place_from_element(element: dict) -> Place | None:
    tags = element.get("tags", {})
    name = tags.get("name")
    if not name:
        return None

    lat = element.get("lat") or element.get("center", {}).get("lat")
    lng = element.get("lon") or element.get("center", {}).get("lon")
    if lat is None or lng is None:
        return None

    category = _category(tags)
    heuristics = _heuristics_for_category(category, tags)
    area = tags.get("addr:suburb") or tags.get("addr:city") or tags.get("addr:neighbourhood") or "Nearby"
    osm_id = f"osm-{element.get('type', 'node')}-{element.get('id')}"

    return Place(
        id=osm_id,
        name=name,
        category=category,
        area=area,
        location=Location(lat=float(lat), lng=float(lng)),
        price_level=heuristics["price_level"],
        typical_spend=heuristics["typical_spend"],
        rating=heuristics["rating"],
        opens_at=heuristics["opens_at"],
        closes_at=heuristics["closes_at"],
        wifi=heuristics["wifi"],
        power=heuristics["power"],
        quietness=heuristics["quietness"],
        seating=heuristics["seating"],
        ambience=heuristics["ambience"],
        food=heuristics["food"],
        parking=tags.get("parking") == "yes",
        security=3,
        outdoor_seating=tags.get("outdoor_seating") == "yes",
        work_friendly=heuristics["work_friendly"],
        date_friendly=heuristics["date_friendly"],
        family_friendly=heuristics["family_friendly"],
        tags=_tags(category, tags),
        data_source="OpenStreetMap",
        photo_url=_photo_url(tags),
        photo_page_url=_photo_page_url(tags),
    )


def _place_from_nominatim_result(item: dict) -> Place | None:
    name = item.get("name") or item.get("display_name", "").split(",")[0]
    lat = item.get("lat")
    lng = item.get("lon")
    if not name or lat is None or lng is None:
        return None

    place_type = item.get("type")
    tags = _tags_from_nominatim_type(place_type)
    tags.update(item.get("extratags") or {})
    category = _category(tags)
    heuristics = _heuristics_for_category(category, tags)
    address = item.get("address", {})
    area = address.get("suburb") or address.get("city_district") or address.get("city") or "Nearby"
    osm_id = f"nominatim-{item.get('osm_type')}-{item.get('osm_id') or item.get('place_id')}"

    return Place(
        id=osm_id,
        name=name,
        category=category,
        area=area,
        location=Location(lat=float(lat), lng=float(lng)),
        price_level=heuristics["price_level"],
        typical_spend=heuristics["typical_spend"],
        rating=heuristics["rating"],
        opens_at=heuristics["opens_at"],
        closes_at=heuristics["closes_at"],
        wifi=heuristics["wifi"],
        power=heuristics["power"],
        quietness=heuristics["quietness"],
        seating=heuristics["seating"],
        ambience=heuristics["ambience"],
        food=heuristics["food"],
        parking=False,
        security=3,
        outdoor_seating=False,
        work_friendly=heuristics["work_friendly"],
        date_friendly=heuristics["date_friendly"],
        family_friendly=heuristics["family_friendly"],
        tags=_tags(category, tags),
        data_source="OpenStreetMap",
        photo_url=_photo_url(tags),
        photo_page_url=_photo_page_url(tags),
    )


def _tags_from_nominatim_type(place_type: str | None) -> dict:
    mapping = {
        "cafe": {"amenity": "cafe"},
        "restaurant": {"amenity": "restaurant"},
        "fast_food": {"amenity": "fast_food"},
        "bar": {"amenity": "bar"},
        "pub": {"amenity": "bar"},
        "library": {"amenity": "library"},
        "park": {"leisure": "park"},
    }
    return mapping.get(place_type or "", {"amenity": "cafe"})


def _category(tags: dict) -> str:
    if tags.get("office") == "coworking":
        return "Coworking"
    mapping = {
        "cafe": "Cafe",
        "restaurant": "Restaurant",
        "fast_food": "Quick food",
        "bar": "Bar",
        "library": "Library",
    }
    amenity = tags.get("amenity")
    if amenity in mapping:
        return mapping[amenity]
    if tags.get("leisure") == "park":
        return "Park"
    return "Place"


def _heuristics_for_category(category: str, tags: dict) -> dict:
    baseline = {
        "price_level": 2,
        "typical_spend": 9000,
        "rating": 3.8,
        "opens_at": 8,
        "closes_at": 22,
        "wifi": 2,
        "power": 2,
        "quietness": 3,
        "seating": 3,
        "ambience": 3,
        "food": 3,
        "work_friendly": 2,
        "date_friendly": 2,
        "family_friendly": 3,
    }
    by_category = {
        "Cafe": {"wifi": 3, "power": 3, "work_friendly": 3, "typical_spend": 8000},
        "Coworking": {"wifi": 4, "power": 5, "quietness": 4, "seating": 4, "work_friendly": 5, "food": 1, "typical_spend": 15000, "price_level": 3},
        "Library": {"quietness": 5, "seating": 4, "work_friendly": 4, "food": 1, "typical_spend": 2000, "price_level": 1},
        "Restaurant": {"food": 4, "ambience": 4, "date_friendly": 4, "typical_spend": 18000, "price_level": 3},
        "Quick food": {"food": 3, "ambience": 2, "typical_spend": 6000, "price_level": 1, "closes_at": 23},
        "Bar": {"quietness": 2, "ambience": 4, "date_friendly": 3, "typical_spend": 16000, "price_level": 3, "opens_at": 12, "closes_at": 24},
        "Park": {"quietness": 3, "ambience": 4, "food": 1, "typical_spend": 3000, "price_level": 1, "opens_at": 7},
    }
    baseline.update(by_category.get(category, {}))

    internet = tags.get("internet_access")
    if internet in {"wlan", "yes"}:
        baseline["wifi"] = 4
    elif internet == "no":
        baseline["wifi"] = 1

    if tags.get("opening_hours") == "24/7":
        baseline["opens_at"] = 0
        baseline["closes_at"] = 24

    return baseline


def _tags(category: str, tags: dict) -> list[str]:
    values = ["live data", "OpenStreetMap", "details limited", category.lower()]
    if tags.get("internet_access") in {"wlan", "yes"}:
        values.append("wifi")
    if tags.get("outdoor_seating") == "yes":
        values.append("outdoor")
    if category in {"Cafe", "Coworking"}:
        values.append("work-friendly")
    if category in {"Restaurant", "Bar"}:
        values.append("date-friendly")
    if _photo_url(tags):
        values.append("photo")
    return values


def _photo_url(tags: dict) -> str | None:
    image = tags.get("image")
    if image and image.startswith(("http://", "https://")):
        return image

    commons = tags.get("wikimedia_commons")
    if commons:
        filename = _commons_filename(commons)
        if filename:
            return f"https://commons.wikimedia.org/wiki/Special:FilePath/{quote(filename)}"

    return None


def _photo_page_url(tags: dict) -> str | None:
    image = tags.get("image")
    if image and image.startswith(("http://", "https://")):
        return image

    commons = tags.get("wikimedia_commons")
    if commons:
        if commons.startswith("Category:"):
            return f"https://commons.wikimedia.org/wiki/{quote(commons.replace(' ', '_'), safe=':/')}"
        filename = _commons_filename(commons)
        if filename:
            return f"https://commons.wikimedia.org/wiki/File:{quote(filename.replace(' ', '_'))}"

    wikidata = tags.get("wikidata")
    if wikidata:
        return f"https://www.wikidata.org/wiki/{quote(wikidata)}"

    return None


def _commons_filename(value: str) -> str | None:
    if value.startswith("File:"):
        return value.removeprefix("File:")
    if "." in value and not value.startswith("Category:"):
        return value
    return None
