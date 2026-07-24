"""
Hotel resilience aggregation and hazard-aware alternative recommendation.
Pure functions over hotel records (backend/db.py) and zone risk data - no
direct DB/HTTP access here, matching the rest of this project's agent
modules (backend/agents/*.py).
"""

# A hotel counts as "operational" if it has the two most critical utilities.
# Internet/generator/battery/solar are resilience *indicators*, not the
# operational bar itself.
OPERATIONAL_UTILITIES = ("electricity_available", "water_available")


def is_operational(hotel: dict) -> bool:
    return all(hotel.get(k, False) for k in OPERATIONAL_UTILITIES)


def compute_resilience_stats(
    hotels: list[dict], zones: list[dict], zone_risk_by_id: dict[str, int]
) -> dict:
    """zones: [{"id","name"}, ...]. zone_risk_by_id: {zone_id: fire_risk_score}."""
    if not hotels:
        return {
            "total_hotels": 0,
            "operational_pct": 0.0,
            "generator_coverage_pct": 0.0,
            "battery_coverage_pct": 0.0,
            "solar_coverage_pct": 0.0,
            "rooms_available_in_safe_zones": 0,
            "zones": [],
            "most_resilient_zone_id": None,
            "most_resilient_zone_name": None,
        }

    total = len(hotels)
    operational = sum(1 for h in hotels if is_operational(h))
    generator = sum(1 for h in hotels if h.get("generator_available"))
    battery = sum(1 for h in hotels if h.get("battery_backup"))
    solar = sum(1 for h in hotels if h.get("solar_panels"))

    zone_names = {z["id"]: z["name"] for z in zones}
    by_zone: dict[str, list[dict]] = {}
    for h in hotels:
        by_zone.setdefault(h["zone_id"], []).append(h)

    zone_summaries = []
    for zone_id, zone_hotels in by_zone.items():
        n = len(zone_hotels)
        op = sum(1 for h in zone_hotels if is_operational(h))
        gen = sum(1 for h in zone_hotels if h.get("generator_available"))
        bat = sum(1 for h in zone_hotels if h.get("battery_backup"))
        sol = sum(1 for h in zone_hotels if h.get("solar_panels"))
        rooms = sum(h.get("rooms_available") or 0 for h in zone_hotels if is_operational(h))
        zone_summaries.append(
            {
                "zone_id": zone_id,
                "zone_name": zone_names.get(zone_id, zone_id),
                "hotel_count": n,
                "operational_pct": round(op / n * 100, 1),
                "generator_coverage_pct": round(gen / n * 100, 1),
                "battery_coverage_pct": round(bat / n * 100, 1),
                "solar_coverage_pct": round(sol / n * 100, 1),
                "rooms_available": rooms,
            }
        )

    zone_summaries.sort(key=lambda z: z["operational_pct"], reverse=True)
    most_resilient = zone_summaries[0] if zone_summaries else None

    # "safe zone" = fire risk_score < 50, same threshold TouristResponse.safe already uses.
    safe_zone_ids = {zid for zid, score in zone_risk_by_id.items() if score < 50}
    rooms_in_safe_zones = sum(
        h.get("rooms_available") or 0
        for h in hotels
        if is_operational(h) and h["zone_id"] in safe_zone_ids
    )

    return {
        "total_hotels": total,
        "operational_pct": round(operational / total * 100, 1),
        "generator_coverage_pct": round(generator / total * 100, 1),
        "battery_coverage_pct": round(battery / total * 100, 1),
        "solar_coverage_pct": round(solar / total * 100, 1),
        "rooms_available_in_safe_zones": rooms_in_safe_zones,
        "zones": zone_summaries,
        "most_resilient_zone_id": most_resilient["zone_id"] if most_resilient else None,
        "most_resilient_zone_name": most_resilient["zone_name"] if most_resilient else None,
    }


def find_hotel_alternative(
    zone_id: str,
    hotel_name: str,
    hotels_by_zone: dict[str, list[dict]],
    neighbor_zone_ids: list[str],
    zone_names: dict[str, str],
) -> dict:
    """
    Implements: "Instead of recommending a hotel currently experiencing a
    power outage, the AI suggests nearby alternatives." Checks same zone
    first, then neighboring zones (from zones.json's neighbors list).
    """
    zone_hotels = hotels_by_zone.get(zone_id, [])
    requested = next((h for h in zone_hotels if h["hotel_name"] == hotel_name), None)

    if requested is None:
        return {
            "requested_hotel": hotel_name,
            "zone_id": zone_id,
            "found": False,
            "is_operational": None,
            "alternatives": [],
            "reason": f"No declared status found for '{hotel_name}' in this zone.",
        }

    if is_operational(requested):
        return {
            "requested_hotel": hotel_name,
            "zone_id": zone_id,
            "found": True,
            "is_operational": True,
            "alternatives": [],
            "reason": "This hotel is currently operational - no alternative needed.",
        }

    same_zone_alts = [
        h for h in zone_hotels if h["hotel_name"] != hotel_name and is_operational(h)
    ]
    alternatives = [
        {
            "hotel_name": h["hotel_name"],
            "zone_id": zone_id,
            "zone_name": zone_names.get(zone_id, zone_id),
            "rooms_available": h.get("rooms_available"),
        }
        for h in same_zone_alts
    ]

    if not alternatives:
        for nz in neighbor_zone_ids:
            for h in hotels_by_zone.get(nz, []):
                if is_operational(h):
                    alternatives.append(
                        {
                            "hotel_name": h["hotel_name"],
                            "zone_id": nz,
                            "zone_name": zone_names.get(nz, nz),
                            "rooms_available": h.get("rooms_available"),
                        }
                    )

    missing = [u for u in OPERATIONAL_UTILITIES if not requested.get(u, False)]
    reason = f"'{hotel_name}' currently lacks: {', '.join(u.replace('_available', '') for u in missing)}."

    return {
        "requested_hotel": hotel_name,
        "zone_id": zone_id,
        "found": True,
        "is_operational": False,
        "alternatives": alternatives[:5],
        "reason": reason,
    }
