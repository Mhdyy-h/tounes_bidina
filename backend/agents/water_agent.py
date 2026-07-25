"""
Water Resource Agent
====================
Predicts water shortages by analyzing reservoir levels, consumption patterns,
tourism demand, historical usage, and weather forecast.

Data sources (current build): simulated — clearly labeled.
"""

import random
from dataclasses import dataclass
from datetime import datetime, timezone

# Reservoir capacity by zone (% fill, simulated seasonal values for July)
RESERVOIR_LEVELS: dict[str, float] = {
    "tunis":       48.0,
    "nabeul":      52.0,
    "beja":        62.0,
    "ain_draham":  71.0,  # Mountain springs, higher levels
    "tabarka":     67.0,
    "sfax":        35.0,  # Historically arid
    "djerba":      28.0,  # Island, chronic stress
    "tozeur":      22.0,  # Desert, critical
    "tataouine":   18.0,  # Deep south, critical
    "el_jem":      41.0,
    "bulla_regia": 58.0,  # Medjerda valley, decent groundwater
    "dougga":      55.0,  # Interior plateau, moderate
    "ichkeul":     64.0,  # Adjacent to Lake Ichkeul / Bizerte water resources
    "hammamet":    50.0,  # Coastal Nabeul governorate, similar to nabeul
    "siliana":     46.0,  # Interior agricultural governorate (Barrage de Siliana dam basin)
}

# Tourism demand multiplier (high season = July)
TOURISM_DEMAND: dict[str, float] = {
    "tunis":       1.2,
    "nabeul":      2.1,   # Peak beach season
    "beja":        0.8,
    "ain_draham":  1.3,
    "tabarka":     1.8,
    "sfax":        0.9,
    "djerba":      2.5,   # Highest tourist density
    "tozeur":      1.1,
    "tataouine":   0.7,
    "el_jem":      1.0,
    "bulla_regia": 0.9,   # Day-trip archaeological site, low overnight demand
    "dougga":      1.0,   # Popular UNESCO day-trip site
    "ichkeul":     0.7,   # Nature reserve, low overnight tourism
    "hammamet":    2.3,   # One of Tunisia's largest beach resort towns
    "siliana":     0.6,   # Remote interior archaeological/hiking area, low overnight demand
}

# Known leak/loss index per zone (0=none, 1=severe infrastructure loss)
LEAK_INDEX: dict[str, float] = {
    "tunis":       0.22,
    "nabeul":      0.18,
    "beja":        0.30,
    "ain_draham":  0.15,
    "tabarka":     0.20,
    "sfax":        0.25,
    "djerba":      0.35,  # Aging island infrastructure
    "tozeur":      0.28,
    "tataouine":   0.32,
    "el_jem":      0.20,
    "bulla_regia": 0.30,  # Rural infrastructure
    "dougga":      0.27,
    "ichkeul":     0.24,
    "hammamet":    0.19,  # Resort-town infrastructure, similar to nabeul
    "siliana":     0.30,  # Rural interior infrastructure, similar to bulla_regia/dougga
}


@dataclass
class WaterFactors:
    reservoir_level_pct: float
    tourism_demand_multiplier: float
    leak_index: float
    temperature_c: float
    estimated_daily_consumption_m3: float


@dataclass
class WaterRisk:
    zone_id: str
    zone_name: str
    shortage_probability: float       # 0-100
    risk_level: str
    regions_under_stress: list[str]
    conservation_recommendations: list[str]
    factors: WaterFactors
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


def _conservation_recommendations(level: str, zone_id: str) -> list[str]:
    base = [
        "Turn off taps when not in use.",
        "Report visible leaks to SONEDE: 81 100 100.",
    ]
    if level in ("high", "critical"):
        base += [
            "Hotels: activate water-saving protocol (linen reuse, flow restrictors).",
            "Restaurants: switch to disposable menus and reduce dishwashing cycles.",
        ]
    if level == "critical":
        base += [
            "CRITICAL: Water rationing possible. Fill emergency reserves now.",
            "Tourist activities involving large water use (water parks, spas) suspended.",
            "Civil protection coordination required for tanker distribution.",
        ]
    return base


def _stressed_regions(zone_id: str, level: str) -> list[str]:
    region_map: dict[str, list[str]] = {
        "djerba":    ["Houmt Souk", "Midoun", "Aghir"],
        "tozeur":    ["Tozeur city", "Nefta", "Degache oasis"],
        "tataouine": ["Tataouine centre", "Ghomrassen"],
        "sfax":      ["Sfax industrial zone", "Skhira"],
    }
    if level == "low":
        return []
    return region_map.get(zone_id, [f"{zone_id.replace('_', ' ').title()} urban centre"])


def _xai_explanation(zone_id: str, factors: WaterFactors, prob: float) -> str:
    drivers = []
    if factors.reservoir_level_pct < 35:
        drivers.append(f"low reservoir fill ({factors.reservoir_level_pct:.0f}%, threshold 35%)")
    if factors.tourism_demand_multiplier > 1.5:
        drivers.append(f"peak tourist season increasing demand by {(factors.tourism_demand_multiplier-1)*100:.0f}%")
    if factors.leak_index > 0.25:
        drivers.append(f"significant infrastructure losses ({factors.leak_index*100:.0f}% network leakage)")
    if factors.temperature_c > 35:
        drivers.append(f"high temperatures ({factors.temperature_c:.1f}°C) accelerating evaporation and consumption")
    if not drivers:
        drivers = ["water supply is within sustainable parameters for current demand"]
    return f"Water shortage probability estimated at {prob:.0f}%: {'; '.join(drivers)}."


def compute_water_risk(
    zone_id: str,
    zone_name: str,
    temperature_c: float | None = None,
) -> WaterRisk:
    temp = temperature_c or 30.0
    reservoir = RESERVOIR_LEVELS.get(zone_id, 50.0) + random.uniform(-3, 3)
    reservoir = max(0.0, min(100.0, reservoir))
    tourism_dem = TOURISM_DEMAND.get(zone_id, 1.0)
    leak = LEAK_INDEX.get(zone_id, 0.2)

    # Estimated daily consumption (m³) — proxy metric for display
    base_consumption = 800 + random.uniform(-50, 50)
    consumption = base_consumption * tourism_dem * (1 + (temp - 20) / 100)

    factors = WaterFactors(
        reservoir_level_pct=round(reservoir, 1),
        tourism_demand_multiplier=round(tourism_dem, 2),
        leak_index=round(leak, 2),
        temperature_c=round(temp, 1),
        estimated_daily_consumption_m3=round(consumption, 0),
    )

    # Scoring model
    reservoir_score = max(0, (60 - reservoir) / 60 * 50)   # 0-50 pts (lower reservoir = higher risk)
    demand_score    = (tourism_dem - 1.0) * 20              # 0-30 pts
    leak_score      = leak * 15                             # 0-15 pts
    temp_score      = max(0, (temp - 28) / 15 * 10)        # 0-10 pts

    raw = reservoir_score + demand_score + leak_score + temp_score
    prob = max(0.0, min(100.0, raw))
    level = _level_from_prob(prob)

    return WaterRisk(
        zone_id=zone_id,
        zone_name=zone_name,
        shortage_probability=round(prob, 1),
        risk_level=level,
        regions_under_stress=_stressed_regions(zone_id, level),
        conservation_recommendations=_conservation_recommendations(level, zone_id),
        factors=factors,
        xai_explanation=_xai_explanation(zone_id, factors, prob),
        is_simulated=True,
        updated_at=datetime.now(timezone.utc).isoformat(),
    )
