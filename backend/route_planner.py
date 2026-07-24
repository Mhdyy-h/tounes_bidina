"""
Smart Tourist Route Planner: real road routing via OSRM's public demo API
(https://router.project-osrm.org, no key required), with hazard-aware
alternative selection layered on top.

Honesty note: OSRM itself has no concept of wildfire/flood/outage risk - it
only knows real road geometry and real drive time. The "safest path" logic
here is ours: we request real alternative routes from OSRM (a genuine feature
of their API - `alternatives=true` - not fabricated), then pick whichever
alternative's actual road geometry passes farthest from zones currently at
high/critical fire risk. If OSRM only has one real route for a given
origin/destination (no genuine alternative exists), that is reported as such
rather than inventing a second route.
"""

import logging
import math

import httpx

logger = logging.getLogger(__name__)

OSRM_BASE = "https://router.project-osrm.org/route/v1/driving"

# How close a route's path needs to pass to a hazardous zone to count as
# "crossing" it, in km. Chosen to roughly match "same immediate area", not
# "same region" - a route 50km away from a fire isn't meaningfully exposed to it.
HAZARD_PROXIMITY_KM = 10

# Real, approximate coordinates for Tunisia's main international airports -
# used as convenient named route origins (e.g. "Airport -> Hotel" per the
# feature's own example). Approximate to the airport terminal area.
AIRPORTS: dict[str, dict] = {
    "tunis_carthage": {"name": "Tunis-Carthage Airport", "lat": 36.8510, "lon": 10.2272},
    "enfidha_hammamet": {"name": "Enfidha-Hammamet Airport", "lat": 36.0757, "lon": 10.4383},
    "monastir": {"name": "Monastir Habib Bourguiba Airport", "lat": 35.7581, "lon": 10.7547},
    "djerba_zarzis": {"name": "Djerba-Zarzis Airport", "lat": 33.8757, "lon": 10.7756},
    "tabarka_ain_draham": {"name": "Tabarka-Aïn Draham Airport", "lat": 36.9787, "lon": 8.8778},
}


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _route_min_distance_to_point(coordinates: list[list[float]], lat: float, lon: float) -> float:
    """coordinates: [[lon, lat], ...] (GeoJSON order, as OSRM returns them)."""
    return min(_haversine_km(lat, lon, c[1], c[0]) for c in coordinates)


def _hazards_crossed(route: dict, hazard_zones: list[dict]) -> list[dict]:
    coords = route["geometry"]["coordinates"]
    hits = []
    for hz in hazard_zones:
        dist = _route_min_distance_to_point(coords, hz["lat"], hz["lon"])
        if dist <= HAZARD_PROXIMITY_KM:
            hits.append(
                {"zone_name": hz["name"], "risk_level": hz["risk_level"], "distance_km": round(dist, 1)}
            )
    return hits


async def plan_route(
    origin_lat: float,
    origin_lon: float,
    dest_lat: float,
    dest_lon: float,
    hazard_zones: list[dict],
) -> dict | None:
    """hazard_zones: [{"lat","lon","name","risk_level"}] - typically zones
    currently at high/critical fire risk. Returns None only if OSRM itself is
    unreachable or returns no route at all - callers must handle that."""
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                f"{OSRM_BASE}/{origin_lon},{origin_lat};{dest_lon},{dest_lat}",
                params={
                    "overview": "full",
                    "geometries": "geojson",
                    "alternatives": "true",
                    "steps": "false",
                },
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:
        logger.warning("OSRM routing failed (%s)", exc)
        return None

    if data.get("code") != "Ok" or not data.get("routes"):
        logger.warning("OSRM returned no usable route: %s", data.get("code"))
        return None

    scored = []
    for r in data["routes"]:
        scored.append(
            {
                "duration_min": round(r["duration"] / 60, 1),
                "distance_km": round(r["distance"] / 1000, 1),
                "geometry": r["geometry"],
                "hazards": _hazards_crossed(r, hazard_zones),
            }
        )

    default_route = scored[0]  # OSRM's primary route - what a normal maps app would give you
    recommended_route = min(scored, key=lambda r: (len(r["hazards"]), r["duration_min"]))
    has_real_alternative = len(scored) > 1
    chose_alternative = recommended_route is not default_route

    return {
        "has_alternative": has_real_alternative,
        "chose_alternative": chose_alternative,
        "default_route": default_route,
        "recommended_route": recommended_route,
        "extra_minutes": round(recommended_route["duration_min"] - default_route["duration_min"], 1),
        "hazards_avoided": default_route["hazards"] if chose_alternative else [],
    }
