"""
Tourism Intelligence Agent
===========================
Knows every tourism resource (hotels, museums, beaches, archaeological sites,
restaurants, festivals, camping areas). Analyzes hazard context, road access,
electricity, water availability, and tourist density to produce safe, smart
routing recommendations.

Instead of: "Road closed"
It outputs: "Take Route B — 12 minutes longer but avoids wildfire risk."
"""

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"


@dataclass
class TouristDestination:
    id: str
    name: str
    zone_id: str
    type: str                     # beach, archaeological_site, nature, cultural, village
    lat: float
    lon: float
    description: str
    activities: list[str]
    amenities: dict               # {hotels, restaurants, hospitals}
    region: str


@dataclass
class TourismRecommendation:
    zone_id: str
    zone_name: str
    overall_safety_score: float   # 0-100 (100 = perfectly safe)
    recommended_destinations: list[dict]
    active_festivals: list[dict]
    smart_routing: list[dict]     # [{from, to, recommended_route, reason}]
    tourist_density: str          # low/medium/high
    accessibility: dict           # {roads_clear: bool, public_transport: bool}
    hazard_summary: dict          # {fire_risk, flood_risk, water_risk, electricity_risk}
    top_recommendation: str       # Natural language smart suggestion
    is_simulated: bool
    updated_at: str


def _load_tourism_data() -> dict:
    try:
        with open(DATA_DIR / "tourism_resources.json", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"destinations": [], "routes": [], "festivals": []}


def _current_month() -> int:
    return datetime.now().month


def _tourist_density(zone_id: str, month: int) -> str:
    """Peak season July-August."""
    beach_zones = {"nabeul", "djerba", "tabarka"}
    if month in (7, 8):
        if zone_id in beach_zones:
            return "high"
        return "medium"
    if month in (6, 9):
        return "medium"
    return "low"


def _smart_routing(zone_id: str, fire_risk: float, flood_risk: float) -> list[dict]:
    """Illustrative route hints for our real 6 zones (previous version referenced
    "beja"/"nabeul"/"tunis" as zone_id conditions, none of which exist in
    zones.json - those branches were dead code that could never fire; fixed to
    use real zone ids). For an ACTUAL computed route with real road geometry
    and real alternative-route selection, see GET /api/route/plan
    (backend/route_planner.py) - this function stays a lightweight, synchronous
    hint generator consistent with the rest of this module."""
    routes = []

    if zone_id == "ain_draham" and fire_risk >= 50:
        routes.append({
            "from": "Béja",
            "to": "Aïn Draham",
            "recommended_route": "Route via Fernana (MC73)",
            "alternative_to": "RN17 direct",
            "extra_time_min": 12,
            "reason": f"RN17 crosses fire risk zone (score {fire_risk:.0f}/100). Detour adds ~12 min but avoids the wildfire area.",
            "confidence": "high",
        })

    if zone_id in ("ain_draham", "bulla_regia") and flood_risk >= 40:
        routes.append({
            "from": "Tunis",
            "to": "Aïn Draham" if zone_id == "ain_draham" else "Bulla Regia",
            "recommended_route": "GP17 via Mateur (higher-ground alternate)",
            "alternative_to": "RN17 Medjerda valley route",
            "extra_time_min": 18,
            "reason": f"Valley roads may flood (flood probability {flood_risk:.0f}%). Mountain alternate stays on high ground.",
            "confidence": "medium",
        })

    if zone_id == "hammamet" and flood_risk >= 30:
        routes.append({
            "from": "Tunis",
            "to": "Hammamet",
            "recommended_route": "A1 motorway (elevated, flood-safe)",
            "alternative_to": "RN1 coastal road",
            "extra_time_min": 5,
            "reason": "Coastal road prone to flooding during heavy rain. A1 motorway is elevated and safer.",
            "confidence": "high",
        })

    return routes


def _top_recommendation(
    zone_id: str,
    zone_name: str,
    safety_score: float,
    destinations: list[dict],
    fire_risk: float,
    flood_risk: float,
) -> str:
    if safety_score >= 75:
        if destinations:
            dest = destinations[0]["name"]
            return f"{dest} is a top pick today — safety score {safety_score:.0f}/100 with no active hazards. Ideal conditions for your visit."
        return f"{zone_name} is safe today (score {safety_score:.0f}/100). All tourist facilities are fully operational."
    if safety_score >= 50:
        top = destinations[0]["name"] if destinations else zone_name
        return f"{top} is accessible with moderate caution. Check road conditions before travel and avoid forest areas."
    if fire_risk > flood_risk:
        return f"⚠ Wildfire risk elevated in {zone_name}. Consider rescheduling or choosing coastal/lowland alternatives."
    return f"⚠ Flood and infrastructure alerts active in {zone_name}. Consider visiting safer alternatives this week."


def compute_tourism_recommendation(
    zone_id: str,
    zone_name: str,
    fire_risk_score: float = 0.0,
    flood_risk_score: float = 0.0,
    water_risk_score: float = 0.0,
    electricity_risk_score: float = 0.0,
) -> TourismRecommendation:
    data = _load_tourism_data()
    month = _current_month()

    # Filter destinations in this zone
    zone_destinations = [
        d for d in data.get("destinations", [])
        if d.get("zone_id") == zone_id
    ]

    # Overall safety = average of inverse risks
    avg_hazard = (fire_risk_score + flood_risk_score + water_risk_score + electricity_risk_score) / 4
    safety_score = max(0.0, 100.0 - avg_hazard)

    # Filter safe destinations (those whose zone risk is below 60)
    recommended = [
        {
            "id": d["id"],
            "name": d["name"],
            "type": d["type"],
            "description": d["description"],
            "activities": d["activities"],
            "amenities": d["amenities"],
            "region": d["region"],
            "lat": d["lat"],
            "lon": d["lon"],
            "safety_tag": "safe" if safety_score >= 60 else ("caution" if safety_score >= 40 else "avoid"),
        }
        for d in zone_destinations
    ]

    # Active festivals this month
    active_festivals = [
        f for f in data.get("festivals", [])
        if f.get("zone_id") == zone_id and f.get("month") == month
    ]

    routing = _smart_routing(zone_id, fire_risk_score, flood_risk_score)
    density = _tourist_density(zone_id, month)

    accessibility = {
        "roads_clear": flood_risk_score < 50 and fire_risk_score < 60,
        "public_transport": electricity_risk_score < 60,
        "road_risk_notes": "No active road closures" if flood_risk_score < 40 and fire_risk_score < 50
                           else "Some roads may be affected — check local updates.",
    }

    hazard_summary = {
        "fire_risk": round(fire_risk_score, 1),
        "flood_risk": round(flood_risk_score, 1),
        "water_risk": round(water_risk_score, 1),
        "electricity_risk": round(electricity_risk_score, 1),
    }

    top = _top_recommendation(zone_id, zone_name, safety_score, recommended, fire_risk_score, flood_risk_score)

    return TourismRecommendation(
        zone_id=zone_id,
        zone_name=zone_name,
        overall_safety_score=round(safety_score, 1),
        recommended_destinations=recommended,
        active_festivals=active_festivals,
        smart_routing=routing,
        tourist_density=density,
        accessibility=accessibility,
        hazard_summary=hazard_summary,
        top_recommendation=top,
        is_simulated=True,
        updated_at=datetime.now(timezone.utc).isoformat(),
    )
