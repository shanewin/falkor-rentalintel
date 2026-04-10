import logging
import math
import requests
from decimal import Decimal
from django.conf import settings
from django.utils import timezone
from .models import Building, NearbySchool

logger = logging.getLogger(__name__)

# Places API (New) — v1 endpoint
PLACES_NEARBY_URL = "https://places.googleapis.com/v1/places:searchNearby"


def _haversine_miles(lat1, lon1, lat2, lon2):
    """Calculate distance in miles between two lat/lng points."""
    R = 3959
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = (math.sin(d_lat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(d_lon / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _places_nearby(lat, lng, included_types, api_key, radius=800, max_results=20):
    """
    Call the Places API (New) Nearby Search endpoint.
    
    included_types: list of place type strings (e.g. ['restaurant', 'cafe'])
    radius: metres (800m ≈ 0.5 mi walkable)
    
    Returns list of place dicts from the 'places' array, or [] on failure.
    """
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        # Request only the fields we actually use to minimise billing
        "X-Goog-FieldMask": (
            "places.displayName,"
            "places.location,"
            "places.rating,"
            "places.types,"
            "places.primaryType"
        ),
    }
    body = {
        "includedTypes": included_types,
        "maxResultCount": max_results,
        "locationRestriction": {
            "circle": {
                "center": {"latitude": lat, "longitude": lng},
                "radius": float(radius),
            }
        },
    }
    try:
        resp = requests.post(PLACES_NEARBY_URL, json=body, headers=headers, timeout=15)
        if resp.status_code == 400:
            logger.warning(
                f"Places API (New) 400 for types={included_types}: {resp.text[:300]}"
            )
            return []
        resp.raise_for_status()
        data = resp.json()
        return data.get("places", [])
    except Exception as e:
        logger.error(f"Places API (New) request failed for types={included_types}: {e}")
        return []


class NeighborhoodService:

    @staticmethod
    def update_building_data(building_id):
        """
        Gateway: refresh all neighbourhood data for a building via
        Google Places API (New).  Building must have latitude + longitude set.
        """
        try:
            building = Building.objects.get(id=building_id)

            if not building.latitude or not building.longitude:
                logger.warning(
                    f"Building {building_id} has no coordinates — skipping neighbourhood update."
                )
                return False

            api_key = getattr(settings, "GOOGLE_PLACES_API_KEY", "")
            if not api_key:
                logger.error("GOOGLE_PLACES_API_KEY is not set in settings.")
                return False

            lat = float(building.latitude)
            lng = float(building.longitude)

            NeighborhoodService._update_scores_from_places(building, lat, lng, api_key)
            NeighborhoodService._update_nearby_schools(building, lat, lng, api_key)

            building.neighborhood_data_updated = timezone.now()
            building.save()

            logger.info(f"Neighbourhood data updated for building {building_id}.")
            return True

        except Exception as e:
            logger.error(
                f"Error updating neighbourhood data for building {building_id}: {e}"
            )
            return False

    # ─────────────────────────────────────────────────────────────────────
    # Walk / Transit / Bike Scores  (derived from POI density)
    # ─────────────────────────────────────────────────────────────────────

    @staticmethod
    def _update_scores_from_places(building, lat, lng, api_key):
        """
        Derives walk, transit, and bike scores from POI density using the
        Places API (New).

        Walk score  — everyday errands within 800 m
        Transit score — public transport options within 1 000 m
        Bike score  — parks / outdoor / bike infrastructure within 1 500 m
        """
        # ── Walkability ───────────────────────────────────────────────────
        walk_places = _places_nearby(
            lat, lng,
            ["grocery_store", "supermarket", "restaurant", "cafe",
             "pharmacy", "bakery", "convenience_store"],
            api_key, radius=800, max_results=20,
        )
        walk_score = min(100, int((len(walk_places) / 25) * 100))

        # ── Transit ───────────────────────────────────────────────────────
        transit_places = _places_nearby(
            lat, lng,
            ["subway_station", "bus_station", "train_station",
             "transit_station", "light_rail_station"],
            api_key, radius=1000, max_results=20,
        )
        transit_score = min(100, int((len(transit_places) / 10) * 100))

        # ── Bikeability ───────────────────────────────────────────────────
        bike_places = _places_nearby(
            lat, lng,
            ["park", "bicycle_store", "gym", "sports_complex"],
            api_key, radius=1500, max_results=20,
        )
        bike_score = min(100, int((len(bike_places) / 15) * 100))

        # ── Descriptions ─────────────────────────────────────────────────
        def walk_desc(s):
            if s >= 90: return "Walker's Paradise"
            if s >= 70: return "Very Walkable"
            if s >= 50: return "Somewhat Walkable"
            return "Car-Dependent"

        def bike_desc(s):
            if s >= 90: return "Biker's Paradise"
            if s >= 70: return "Very Bikeable"
            if s >= 50: return "Bikeable"
            return "Minimal Bike Infrastructure"

        def transit_desc(s):
            if s >= 90: return "Rider's Paradise"
            if s >= 70: return "Excellent Transit"
            if s >= 50: return "Good Transit"
            return "Minimal Transit"

        building.walk_score = walk_score
        building.walk_description = walk_desc(walk_score)
        building.bike_score = bike_score
        building.bike_description = bike_desc(bike_score)
        building.transit_score = transit_score
        building.transit_description = transit_desc(transit_score)
        building.save(update_fields=[
            "walk_score", "walk_description",
            "bike_score", "bike_description",
            "transit_score", "transit_description",
        ])

        logger.info(
            f"Building {building.id} scores — "
            f"walk={walk_score} ({len(walk_places)} POIs), "
            f"transit={transit_score} ({len(transit_places)} POIs), "
            f"bike={bike_score} ({len(bike_places)} POIs)"
        )

    # ─────────────────────────────────────────────────────────────────────
    # Nearby Schools
    # ─────────────────────────────────────────────────────────────────────

    @staticmethod
    def _update_nearby_schools(building, lat, lng, api_key):
        """
        Fetches nearby schools via Places API (New), computes distance, and
        stores up to 8 results in NearbySchool.

        Rating: Google's 1–5 star rating is scaled to 1–10.
        Grade level: inferred from primaryType / types list.
        """
        results = _places_nearby(
            lat, lng,
            ["school", "primary_school", "secondary_school"],
            api_key, radius=2000, max_results=20,
        )

        building.nearby_schools.all().delete()

        created = 0
        seen_names = set()

        for place in results:
            name = place.get("displayName", {}).get("text", "Unknown School")

            # De-duplicate by name (API may return same school for multiple types)
            if name in seen_names:
                continue
            seen_names.add(name)

            loc = place.get("location", {})
            place_lat = loc.get("latitude")
            place_lng = loc.get("longitude")
            if place_lat is None or place_lng is None:
                continue

            distance_miles = _haversine_miles(lat, lng, place_lat, place_lng)

            # Scale 1–5 stars → 1–10
            google_rating = place.get("rating")
            rating = round(google_rating * 2) if google_rating else None

            # Grade level from primaryType
            primary_type = place.get("primaryType", "")
            types = place.get("types", [])

            if "secondary_school" in (primary_type, *types):
                grades = "9–12"
            elif "middle_school" in (primary_type, *types):
                grades = "6–8"
            elif "primary_school" in (primary_type, *types):
                grades = "PK–5"
            else:
                grades = "K–12"

            # School type heuristic
            name_lower = name.lower()
            if any(kw in name_lower for kw in [
                "academy", "prep", "montessori", "jewish", "catholic",
                "christian", "yeshiva", "hebrew", "private",
            ]):
                school_type = "Private"
            elif any(kw in name_lower for kw in ["charter"]):
                school_type = "Charter"
            else:
                school_type = "Public"

            try:
                NearbySchool.objects.create(
                    building=building,
                    name=name,
                    rating=rating,
                    grades=grades,
                    distance=Decimal(str(round(distance_miles, 2))),
                    school_type=school_type,
                )
                created += 1
                if created >= 8:
                    break
            except Exception as e:
                logger.warning(f"Could not save school '{name}': {e}")

        logger.info(f"Saved {created} nearby schools for building {building.id}.")
