"""
Flood Intelligence Agent
========================
Analyzes rainfall, terrain elevation, rivers, drainage, soil saturation, and
historical flood data to predict flood risk, flooded roads, hotels at risk,
and evacuation recommendations.

Data sources (current build): simulated — clearly labeled.
"""

import math
import random
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import json

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"

# Historical flood frequency per zone (0-1 scale, from historical records)
# ain_draham/bulla_regia/dougga/tabarka are all in the Medjerda watershed region
# (Jendouba/Beja governorates) - real flood history there (see beja's 0.55).
HISTORICAL_FLOOD_FREQ: dict[str, float] = {
    "tunis":       0.25,
    "nabeul":      0.30,
    "beja":        0.55,
    "ain_draham":  0.65,   # Mountain watershed, highest flood risk
    "tabarka":     0.50,
    "sfax":        0.20,
    "djerba":      0.15,
    "tozeur":      0.10,
    "tataouine":   0.08,
    "el_jem":      0.22,
    "bulla_regia": 0.45,   # Medjerda valley floor near Jendouba - real flood-prone river valley
    "dougga":      0.20,   # UNESCO hilltop site, ~571m elevation - naturally low flood exposure
    "ichkeul":     0.35,   # Lake/wetland basin (Bizerte) - surrounding low ground floods, not the lake itself
    "hammamet":    0.30,   # Coastal Nabeul governorate - same historical flood exposure as nabeul
    "siliana":     0.25,   # Interior Dorsale-mountain plateau, dryland cereal region - occasional oued flash floods
}

# Terrain elevation class per zone: "low" | "mid" | "high"
TERRAIN_CLASS: dict[str, str] = {
    "tunis":       "low",
    "nabeul":      "low",
    "beja":        "mid",
    "ain_draham":  "high",
    "tabarka":     "mid",
    "sfax":        "low",
    "djerba":      "low",
    "tozeur":      "low",
    "tataouine":   "mid",
    "el_jem":      "low",
    "bulla_regia": "low",   # Medjerda valley floor
    "dougga":      "high",  # Hilltop/plateau site
    "ichkeul":     "low",   # Lake basin
    "hammamet":    "low",   # Coastal
    "siliana":     "mid",   # Interior plateau on the western Dorsale range
}

# Drainage quality index per zone (0=poor,1=excellent)
DRAINAGE_INDEX: dict[str, float] = {
    "tunis":       0.60,
    "nabeul":      0.55,
    "beja":        0.35,
    "ain_draham":  0.30,
    "tabarka":     0.40,
    "sfax":        0.65,
    "djerba":      0.70,
    "tozeur":      0.80,
    "tataouine":   0.75,
    "el_jem":      0.60,
    "bulla_regia": 0.35,   # Rural, limited infrastructure investment
    "dougga":      0.55,   # Elevated terrain aids natural runoff
    "ichkeul":     0.45,   # Wetland buffers some, but surrounding roads poorly drained
    "hammamet":    0.55,   # Resort-town infrastructure, similar to nabeul
    "siliana":     0.40,   # Rural interior governorate, modest infrastructure investment
}


@dataclass
class FloodFactors:
    rainfall_mm: float
    soil_saturation_pct: float
    drainage_index: float
    historical_freq: float
    terrain_class: str  # "low" | "mid" | "high"


@dataclass
class FloodRisk:
    zone_id: str
    zone_name: str
    flood_probability: float          # 0-100
    risk_level: str                   # low/medium/high/critical
    flooded_roads: list[str]
    hotels_at_risk: int
    evacuation_recommendations: list[str]
    factors: FloodFactors
    xai_explanation: str
    is_simulated: bool
    updated_at: str


def _terrain_multiplier(terrain: str) -> float:
    return {"low": 1.4, "mid": 1.0, "high": 0.7}.get(terrain, 1.0)


def _level_from_prob(p: float) -> str:
    if p >= 70:
        return "critical"
    if p >= 50:
        return "high"
    if p >= 30:
        return "medium"
    return "low"


def _flooded_roads(zone_id: str, prob: float) -> list[str]:
    if prob < 30:
        return []
    road_map: dict[str, list[str]] = {
        "ain_draham":  ["RN17 Jendouba–Aïn Draham (km 34–47)", "RP62 Forest loop road"],
        "beja":        ["GP6 Beja bypass", "MC57 rural connector"],
        "tabarka":     ["RN7 coastal section", "RP71 bridge crossing"],
        "tunis":       ["GP1 underpass (La Goulette)", "Boulevard du 7 Novembre (sector 3)"],
        "nabeul":      ["GP1 Hammamet–Nabeul interchange"],
        "bulla_regia": ["MC59 Jendouba–Bulla Regia access road", "Medjerda river crossing"],
        "dougga":      ["MC65 Téboursouk–Dougga approach road"],
        "ichkeul":     ["RN11 Bizerte–Mateur lakeside section"],
        "hammamet":    ["GP1 Hammamet–Nabeul interchange", "Avenue de la République (Hammamet centre)"],
        "siliana":     ["RN12 Siliana–Gaâfour section", "MC71 Makthar approach road"],
    }
    roads = road_map.get(zone_id, [f"Secondary road in {zone_id.replace('_', ' ').title()}"])
    if prob >= 70:
        return roads
    return roads[:1] if roads else []


def _evacuation_recommendations(zone_id: str, prob: float, level: str) -> list[str]:
    if level == "low":
        return ["No evacuation needed. Monitor weather updates."]
    if level == "medium":
        return [
            "Avoid low-lying roads and underpasses.",
            "Keep emergency contacts handy.",
            "Monitor Météo Tunisie for updated alerts.",
        ]
    if level == "high":
        return [
            "Move to higher ground if in flood-prone areas.",
            "Avoid all watercourses and dry riverbeds (oueds).",
            "Follow civil protection instructions.",
            "Hotels near rivers: activate flood protocol.",
        ]
    return [
        "IMMEDIATE: Evacuate flood zones to designated shelters.",
        "Do NOT attempt to cross flooded roads.",
        "Civil protection contact: 198 (emergency).",
        "All tourist activities in zone suspended.",
    ]


def _xai_explanation(zone_id: str, factors: FloodFactors, prob: float) -> str:
    drivers = []
    if factors.rainfall_mm > 40:
        drivers.append(f"heavy rainfall ({factors.rainfall_mm:.0f} mm in 24h, threshold 40 mm)")
    if factors.soil_saturation_pct > 65:
        drivers.append(f"high soil saturation ({factors.soil_saturation_pct:.0f}%, reducing absorption capacity)")
    if factors.drainage_index < 0.4:
        drivers.append(f"poor drainage infrastructure (index {factors.drainage_index:.2f})")
    if factors.historical_freq > 0.4:
        drivers.append(f"historically flood-prone zone (frequency {factors.historical_freq*100:.0f}%)")
    if factors.terrain_class == "low":
        drivers.append("low-lying terrain with limited natural runoff")
    if not drivers:
        drivers = ["current conditions are within normal parameters"]
    joined = "; ".join(drivers)
    return f"Flood probability estimated at {prob:.0f}% because: {joined}."


def compute_flood_risk(
    zone_id: str,
    zone_name: str,
    rainfall_mm: float | None = None,
    humidity_pct: float | None = None,
) -> FloodRisk:
    """
    Computes flood risk for a zone.
    rainfall_mm and humidity_pct may come from the weather API (passed in from main.py).
    Any unknown zone falls back to conservative defaults.
    """
    # Derive soil saturation from humidity as a proxy
    sat = (humidity_pct or 55.0) * 0.9 + random.uniform(-3, 3)
    sat = max(0.0, min(100.0, sat))

    rain = rainfall_mm if rainfall_mm is not None else random.uniform(0, 25)
    terrain = TERRAIN_CLASS.get(zone_id, "mid")
    drainage = DRAINAGE_INDEX.get(zone_id, 0.5)
    hist_freq = HISTORICAL_FLOOD_FREQ.get(zone_id, 0.2)

    factors = FloodFactors(
        rainfall_mm=round(rain, 1),
        soil_saturation_pct=round(sat, 1),
        drainage_index=drainage,
        historical_freq=hist_freq,
        terrain_class=terrain,
    )

    # Scoring model
    rain_score   = min(rain / 80 * 40, 40)                      # 0-40 pts
    sat_score    = (sat / 100) * 20                              # 0-20 pts
    drain_score  = (1 - drainage) * 15                          # 0-15 pts
    hist_score   = hist_freq * 15                               # 0-15 pts
    terrain_adj  = _terrain_multiplier(terrain)

    raw = (rain_score + sat_score + drain_score + hist_score) * terrain_adj
    prob = max(0.0, min(100.0, raw))

    level = _level_from_prob(prob)
    roads = _flooded_roads(zone_id, prob)
    hotels_at_risk = max(0, int(prob / 30))
    evac = _evacuation_recommendations(zone_id, prob, level)
    xai = _xai_explanation(zone_id, factors, prob)

    return FloodRisk(
        zone_id=zone_id,
        zone_name=zone_name,
        flood_probability=round(prob, 1),
        risk_level=level,
        flooded_roads=roads,
        hotels_at_risk=hotels_at_risk,
        evacuation_recommendations=evac,
        factors=factors,
        xai_explanation=xai,
        is_simulated=True,
        updated_at=datetime.now(timezone.utc).isoformat(),
    )
