"""
Electricity & Infrastructure Agent
====================================
Monitors electricity availability using hotel declarations, Famma Dhaw reports,
generator status, battery/solar production. Tracks outages, forecasts recovery,
identifies resilient tourism zones.

Data sources (current build): simulated — clearly labeled.
"""

import random
from dataclasses import dataclass
from datetime import datetime, timezone

# Grid reliability index per zone (0=unreliable, 1=fully reliable, July 2026 context)
GRID_RELIABILITY: dict[str, float] = {
    "tunis":       0.95,
    "nabeul":      0.88,
    "beja":        0.80,
    "ain_draham":  0.72,   # Mountain zone, older grid
    "tabarka":     0.78,
    "sfax":        0.87,
    "djerba":      0.82,
    "tozeur":      0.74,
    "tataouine":   0.65,   # Remote, lower reliability
    "el_jem":      0.84,
    "bulla_regia": 0.73,   # Rural Medjerda valley, older grid like ain_draham
    "dougga":      0.76,   # Interior plateau, moderate
    "ichkeul":     0.79,   # Near Bizerte/Menzel Bourguiba urban grid
    "hammamet":    0.90,   # Major resort town, high infrastructure investment like nabeul
}

# Hotel backup power coverage (% hotels with generators or solar)
HOTEL_BACKUP_PCT: dict[str, float] = {
    "tunis":       0.80,
    "nabeul":      0.85,
    "beja":        0.50,
    "ain_draham":  0.60,
    "tabarka":     0.65,
    "sfax":        0.75,
    "djerba":      0.90,   # Large resort area, high investment
    "tozeur":      0.70,
    "tataouine":   0.55,
    "el_jem":      0.65,
    "bulla_regia": 0.40,   # Few hotels, day-trip archaeological site
    "dougga":      0.45,   # Few hotels, day-trip UNESCO site
    "ichkeul":     0.40,   # Few hotels, nature reserve
    "hammamet":    0.82,   # Large resort hotels typically carry generators
}

# Solar production index per zone (July, 0-1)
SOLAR_INDEX: dict[str, float] = {
    "tunis":       0.70,
    "nabeul":      0.75,
    "beja":        0.65,
    "ain_draham":  0.55,
    "tabarka":     0.60,
    "sfax":        0.85,
    "djerba":      0.88,
    "tozeur":      0.95,   # Desert, maximum solar
    "tataouine":   0.92,
    "el_jem":      0.80,
    "bulla_regia": 0.68,
    "dougga":      0.70,
    "ichkeul":     0.62,
    "hammamet":    0.76,
}

# Known ongoing outages (simulated for demo — in production: from Famma Dhaw API)
SIMULATED_OUTAGES: dict[str, dict] = {
    "ain_draham": {
        "active": False,
        "affected_area": "Northern sector",
        "started_at": None,
        "estimated_recovery_h": None,
    },
    "tataouine": {
        "active": False,
        "affected_area": None,
        "started_at": None,
        "estimated_recovery_h": None,
    },
}


@dataclass
class ElectricityFactors:
    grid_reliability: float
    hotel_backup_pct: float
    solar_index: float
    active_outage: bool
    peak_load_factor: float  # >1 means grid under stress


@dataclass
class ElectricityRisk:
    zone_id: str
    zone_name: str
    outage_probability: float          # 0-100
    risk_level: str
    active_outage: bool
    outage_affected_area: str | None
    estimated_recovery_hours: int | None
    resilient_tourism_zones: list[str]
    hotel_availability_pct: float
    xai_explanation: str
    is_simulated: bool
    outage_source: str                  # where active_outage actually came from
    outage_reports: dict | None          # raw Famma Dhaw report counts, if real data was used
    updated_at: str


def _level_from_prob(p: float) -> str:
    if p >= 70:
        return "critical"
    if p >= 50:
        return "high"
    if p >= 30:
        return "medium"
    return "low"


def _resilient_zones(zone_id: str, backup: float, solar: float) -> list[str]:
    """Identify sub-zones that are resilient (high backup + solar)."""
    resilience = (backup + solar) / 2
    resilience_map: dict[str, list[str]] = {
        "djerba":    ["Djerba Resort Zone (Zone Touristique)", "Houmt Souk centre"],
        "nabeul":    ["Hammamet Sud resort corridor", "Yasmine Hammamet"],
        "hammamet":  ["Hammamet Sud resort corridor", "Yasmine Hammamet"],
        "tunis":     ["Les Berges du Lac", "Gammarth hotels"],
        "tozeur":    ["Tozeur hotel zone (Route Touristique)"],
        "sfax":      ["Sfax city centre", "Sfax business district"],
    }
    if resilience < 0.65:
        return []
    return resilience_map.get(zone_id, [f"{zone_id.replace('_',' ').title()} main hotel area"])


def _xai_explanation(zone_id: str, factors: ElectricityFactors, prob: float) -> str:
    drivers = []
    if factors.active_outage:
        drivers.append("active outage currently registered in this zone")
    if factors.grid_reliability < 0.75:
        drivers.append(f"aging grid infrastructure (reliability {factors.grid_reliability*100:.0f}%)")
    if factors.peak_load_factor > 1.1:
        drivers.append(f"grid under peak load stress (factor {factors.peak_load_factor:.2f}× normal)")
    if factors.hotel_backup_pct < 0.6:
        drivers.append(f"limited hotel backup power ({factors.hotel_backup_pct*100:.0f}% with generators/solar)")
    if factors.solar_index > 0.8:
        drivers.append(f"high solar offset reducing grid dependency ({factors.solar_index*100:.0f}% solar capacity)")
    if not drivers:
        drivers = ["grid conditions are normal and stable"]
    return f"Electricity outage probability estimated at {prob:.0f}%: {'; '.join(drivers)}."


def compute_electricity_risk(
    zone_id: str,
    zone_name: str,
    temperature_c: float | None = None,
    real_outage: dict | None = None,
) -> ElectricityRisk:
    """
    `real_outage`, if given, is the dict returned by
    backend.famma_dhaw_client.get_zone_outage_status() - real, crowd-sourced
    outage status. When present and matched, it REPLACES the simulated
    active_outage flag; grid_reliability/hotel_backup/solar_index remain
    simulated regardless (no real source for those), so `is_simulated` stays
    True for the model overall, and `outage_source` names exactly what's real.
    """
    temp = temperature_c or 30.0
    reliability = GRID_RELIABILITY.get(zone_id, 0.80) + random.uniform(-0.03, 0.03)
    reliability = max(0.0, min(1.0, reliability))
    backup = HOTEL_BACKUP_PCT.get(zone_id, 0.65)
    solar = SOLAR_INDEX.get(zone_id, 0.70)

    outage_reports = None
    if real_outage is not None and real_outage.get("status") != "no_data":
        status = real_outage["status"]
        active_outage = status in ("cut", "contested")
        area_note = real_outage.get("famma_dhaw_name")
        outage_affected_area = area_note if active_outage else None
        estimated_recovery_h = None  # Famma Dhaw doesn't report recovery ETAs, only current status
        match_note = "exact location" if real_outage.get("is_exact_location_match") else "nearest tracked municipality"
        outage_source = (
            f"REAL - Famma Dhaw community reports ({match_note}: {area_note}, "
            f"{real_outage.get('off_count', 0)} cut-reports vs {real_outage.get('on_count', 0)} "
            f"working-reports, last updated {real_outage.get('last_report')}). "
            "Unofficial crowd-sourced data - cross-reference with STEG."
        )
        outage_reports = {
            "off_count": real_outage.get("off_count"),
            "on_count": real_outage.get("on_count"),
            "status": status,
            "last_report": real_outage.get("last_report"),
        }
    else:
        outage_info = SIMULATED_OUTAGES.get(zone_id, {})
        active_outage = outage_info.get("active", False)
        outage_affected_area = outage_info.get("affected_area")
        estimated_recovery_h = outage_info.get("estimated_recovery_h")
        outage_source = "SIMULATED - no Famma Dhaw match for this zone, or fetch unavailable"

    # Peak load factor: summer heat → ACs → grid stress
    peak_factor = 1.0 + max(0, (temp - 30) / 30) * 0.4

    factors = ElectricityFactors(
        grid_reliability=round(reliability, 2),
        hotel_backup_pct=round(backup, 2),
        solar_index=round(solar, 2),
        active_outage=active_outage,
        peak_load_factor=round(peak_factor, 2),
    )

    # Scoring model
    base_outage = (1 - reliability) * 60           # 0-60 pts
    load_penalty = max(0, (peak_factor - 1.0)) * 20  # 0-20 pts
    backup_offset = backup * -10                    # -10 to 0 pts (backup reduces risk)
    outage_bonus = 40 if active_outage else 0

    raw = base_outage + load_penalty + backup_offset + outage_bonus
    prob = max(0.0, min(100.0, raw))
    level = _level_from_prob(prob)

    hotel_avail = min(100.0, backup * 100 + (1 - prob / 200) * 20)
    resilient = _resilient_zones(zone_id, backup, solar)

    return ElectricityRisk(
        zone_id=zone_id,
        zone_name=zone_name,
        outage_probability=round(prob, 1),
        risk_level=level,
        active_outage=active_outage,
        outage_affected_area=outage_affected_area,
        estimated_recovery_hours=estimated_recovery_h,
        resilient_tourism_zones=resilient,
        hotel_availability_pct=round(hotel_avail, 1),
        xai_explanation=_xai_explanation(zone_id, factors, prob),
        is_simulated=True,
        outage_source=outage_source,
        outage_reports=outage_reports,
        updated_at=datetime.now(timezone.utc).isoformat(),
    )
