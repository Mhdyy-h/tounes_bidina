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
) -> ElectricityRisk:
    temp = temperature_c or 30.0
    reliability = GRID_RELIABILITY.get(zone_id, 0.80) + random.uniform(-0.03, 0.03)
    reliability = max(0.0, min(1.0, reliability))
    backup = HOTEL_BACKUP_PCT.get(zone_id, 0.65)
    solar = SOLAR_INDEX.get(zone_id, 0.70)
    outage_info = SIMULATED_OUTAGES.get(zone_id, {})
    active_outage = outage_info.get("active", False)

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
        outage_affected_area=outage_info.get("affected_area"),
        estimated_recovery_hours=outage_info.get("estimated_recovery_h"),
        resilient_tourism_zones=resilient,
        hotel_availability_pct=round(hotel_avail, 1),
        xai_explanation=_xai_explanation(zone_id, factors, prob),
        is_simulated=True,
        updated_at=datetime.now(timezone.utc).isoformat(),
    )
