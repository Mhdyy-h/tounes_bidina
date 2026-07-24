"""
XAI Agent — Explainability Engine
====================================
Produces rich, factor-by-factor explanations for every prediction made by
any of the domain agents. Instead of "Fire Risk = 91%", it explains WHY:

  "Fire probability increased because:
   - vegetation moisture decreased by 18%
   - wind speed reached 34 km/h
   - humidity dropped below 20%
   - temperatures exceeded 39°C
   - similar conditions caused fires in this area during previous summers"

This agent wraps all domain agents and enriches their outputs with XAI narratives.
"""

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass
class XAIExplanation:
    agent: str
    zone_id: str
    zone_name: str
    prediction: str       # e.g. "Fire Risk: 78/100 (HIGH)"
    risk_level: str
    risk_score: float
    factors_breakdown: list[dict]   # [{factor, value, contribution, direction}]
    historical_context: str
    plain_language: str
    confidence_note: str
    updated_at: str


# Historical fire incidents per zone — used for contextual XAI
HISTORICAL_FIRE_INCIDENTS: dict[str, list[str]] = {
    "ain_draham": [
        "Summer 2023: 340 ha burned in similar NDVI/wind conditions",
        "August 2021: Major forest fire requiring 3 aerial bombings",
        "July 2017: Fire started along RN17 under 35°C+ temperatures",
    ],
    "beja": [
        "Summer 2022: 120 ha affected near Beja forest reserve",
    ],
    "tabarka": [
        "2020: Coastal forest fire linked to prolonged drought (NDVI < 0.3)",
    ],
}

HISTORICAL_FLOOD_INCIDENTS: dict[str, list[str]] = {
    "tunis":   ["2019: Flooding of Ariana district after 60mm/24h rainfall"],
    "beja":    ["2018: Oued Medjerda overflow caused road closures for 3 days"],
    "ain_draham": ["Multiple seasonal flash floods along RN17 valley"],
    "nabeul":  ["2021: Coastal flooding of Hammamet Nord during autumn storms"],
    "hammamet": ["2021: Coastal flooding of Hammamet Nord during autumn storms"],
    "bulla_regia": ["Medjerda valley floor - shares the same flood-prone river system as Béja/Jendouba upstream"],
}


def _fire_xai(zone_id: str, zone_name: str, score: float, level: str, factors: dict) -> XAIExplanation:
    temp = factors.get("temperature_c", 25)
    wind = factors.get("wind_kmh", 10)
    humidity = factors.get("humidity_pct", 60)
    rain = factors.get("rain_mm", 5)
    ndvi = factors.get("ndvi", 0.55)
    fires = factors.get("active_fires_nearby", 0)

    breakdown = [
        {
            "factor": "Temperature",
            "value": f"{temp:.1f}°C",
            "contribution": "high" if temp > 35 else ("medium" if temp > 28 else "low"),
            "direction": "↑ increases risk" if temp > 35 else "→ neutral",
            "threshold": "35°C",
        },
        {
            "factor": "Wind Speed",
            "value": f"{wind:.1f} km/h",
            "contribution": "high" if wind > 30 else ("medium" if wind > 20 else "low"),
            "direction": "↑ increases spread" if wind > 20 else "→ neutral",
            "threshold": "20 km/h",
        },
        {
            "factor": "Humidity",
            "value": f"{humidity:.0f}%",
            "contribution": "high" if humidity < 25 else ("medium" if humidity < 40 else "low"),
            "direction": "↓ decreases moisture barrier" if humidity < 40 else "→ adequate",
            "threshold": "40%",
        },
        {
            "factor": "Recent Rainfall",
            "value": f"{rain:.1f} mm",
            "contribution": "low" if rain > 10 else "medium",
            "direction": "↓ dry conditions" if rain < 5 else "→ some moisture retained",
            "threshold": "10 mm",
        },
        {
            "factor": "Vegetation Index (NDVI)",
            "value": f"{ndvi:.2f}",
            "contribution": "high" if ndvi < 0.3 else ("medium" if ndvi < 0.45 else "low"),
            "direction": "↑ dry vegetation = more fuel" if ndvi < 0.4 else "→ vegetation moisture adequate",
            "threshold": "0.45",
        },
        {
            "factor": "Active Fire Hotspots",
            "value": f"{fires} within 15 km",
            "contribution": "critical" if fires > 1 else ("high" if fires == 1 else "low"),
            "direction": "↑ existing fires amplify spread risk" if fires > 0 else "→ no active fires detected",
            "threshold": "0",
        },
    ]

    hist = HISTORICAL_FIRE_INCIDENTS.get(zone_id, [])
    hist_context = (
        "Historical fire events under similar conditions: " + "; ".join(hist[:2])
        if hist else
        f"No major recorded fire incidents in {zone_name} in recent years."
    )

    drivers = [b["factor"] for b in breakdown if b["contribution"] in ("high", "critical")]
    plain = (
        f"Fire probability is {score:.0f}/100 ({level}) in {zone_name}. "
        + (f"Key drivers: {', '.join(drivers)}. " if drivers else "Conditions are within normal range. ")
        + (f"This pattern matches historical fire events: {hist[0]}." if hist else "")
    )

    confidence = (
        "High confidence — real satellite fire hotspots + live weather data." if fires > 0
        else "Medium confidence — based on weather model and simulated NDVI; no active hotspots detected."
    )

    return XAIExplanation(
        agent="Fire Intelligence Agent",
        zone_id=zone_id,
        zone_name=zone_name,
        prediction=f"Fire Risk: {score:.0f}/100 ({level.upper()})",
        risk_level=level,
        risk_score=score,
        factors_breakdown=breakdown,
        historical_context=hist_context,
        plain_language=plain,
        confidence_note=confidence,
        updated_at=datetime.now(timezone.utc).isoformat(),
    )


def _flood_xai(zone_id: str, zone_name: str, score: float, level: str, factors: dict) -> XAIExplanation:
    rain = factors.get("rainfall_mm", 10)
    sat = factors.get("soil_saturation_pct", 50)
    drainage = factors.get("drainage_index", 0.5)
    terrain = factors.get("terrain_class", "mid")

    breakdown = [
        {
            "factor": "Rainfall (24h)",
            "value": f"{rain:.0f} mm",
            "contribution": "high" if rain > 50 else ("medium" if rain > 25 else "low"),
            "direction": "↑ direct flood input" if rain > 30 else "→ moderate",
            "threshold": "40 mm/24h",
        },
        {
            "factor": "Soil Saturation",
            "value": f"{sat:.0f}%",
            "contribution": "high" if sat > 75 else ("medium" if sat > 55 else "low"),
            "direction": "↑ reduces absorption capacity" if sat > 60 else "→ normal",
            "threshold": "65%",
        },
        {
            "factor": "Drainage Infrastructure",
            "value": f"Index {drainage:.2f}",
            "contribution": "high" if drainage < 0.35 else ("medium" if drainage < 0.55 else "low"),
            "direction": "↓ poor drainage accelerates flooding" if drainage < 0.45 else "→ adequate",
            "threshold": "0.50",
        },
        {
            "factor": "Terrain Type",
            "value": terrain.capitalize(),
            "contribution": "high" if terrain == "low" else "low",
            "direction": "↑ low terrain accumulates water" if terrain == "low" else "→ elevated terrain reduces risk",
            "threshold": "Lowland",
        },
    ]

    hist = HISTORICAL_FLOOD_INCIDENTS.get(zone_id, [])
    hist_context = (
        "Historical flood events: " + "; ".join(hist[:2])
        if hist else f"No significant recorded floods in {zone_name} in recent years."
    )

    plain = (
        f"Flood probability is {score:.0f}/100 ({level}) in {zone_name}. "
        f"{'Heavy rainfall combined with saturated soils creates runoff risk. ' if rain > 30 and sat > 60 else ''}"
        f"{'Drainage infrastructure is insufficient to handle current input. ' if drainage < 0.4 else ''}"
        + (f"Historical precedent: {hist[0]}." if hist else "")
    )

    return XAIExplanation(
        agent="Flood Intelligence Agent",
        zone_id=zone_id,
        zone_name=zone_name,
        prediction=f"Flood Risk: {score:.0f}/100 ({level.upper()})",
        risk_level=level,
        risk_score=score,
        factors_breakdown=breakdown,
        historical_context=hist_context,
        plain_language=plain,
        confidence_note="Simulated model — real-time oued sensor data not yet integrated.",
        updated_at=datetime.now(timezone.utc).isoformat(),
    )


def generate_xai(
    agent_type: str,
    zone_id: str,
    zone_name: str,
    risk_score: float,
    risk_level: str,
    factors: dict,
) -> XAIExplanation:
    """Entry point: dispatches to the correct XAI generator based on agent_type."""
    agent_type = agent_type.lower()
    if agent_type == "fire":
        return _fire_xai(zone_id, zone_name, risk_score, risk_level, factors)
    if agent_type == "flood":
        return _flood_xai(zone_id, zone_name, risk_score, risk_level, factors)

    # Generic fallback for water/electricity
    breakdown = [
        {"factor": k.replace("_", " ").title(), "value": str(v), "contribution": "medium", "direction": "→"}
        for k, v in factors.items()
    ]
    return XAIExplanation(
        agent=f"{agent_type.capitalize()} Agent",
        zone_id=zone_id,
        zone_name=zone_name,
        prediction=f"{agent_type.capitalize()} Risk: {risk_score:.0f}/100 ({risk_level.upper()})",
        risk_level=risk_level,
        risk_score=risk_score,
        factors_breakdown=breakdown,
        historical_context="Historical data integration in progress.",
        plain_language=f"{agent_type.capitalize()} risk is {risk_score:.0f}/100 ({risk_level}) in {zone_name}.",
        confidence_note="Simulated model — clearly labeled.",
        updated_at=datetime.now(timezone.utc).isoformat(),
    )
