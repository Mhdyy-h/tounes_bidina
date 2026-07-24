"""
Emergency Optimization Agent
==============================
Optimizes the allocation of emergency resources: firefighters, ambulances,
police, civil protection teams, helicopters, and water trucks.

Uses a priority-weighted allocation algorithm based on zone risk scores across
all active hazard types. Returns deployment recommendations, response time
estimates, and resource requirements per zone.

Data sources (current build): simulated capacity values — clearly labeled.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone

# Regional resource pools (simulated for Tunisia's real structure)
REGIONAL_RESOURCES = {
    "firefighters":   {"total": 240, "unit": "teams of 4"},
    "ambulances":     {"total": 85,  "unit": "vehicles"},
    "police":         {"total": 300, "unit": "officers"},
    "civil_protection": {"total": 120, "unit": "personnel"},
    "helicopters":    {"total": 6,   "unit": "aircraft"},
    "water_trucks":   {"total": 40,  "unit": "vehicles"},
}

# Base response time by resource type (minutes from nearest depot)
BASE_RESPONSE_TIME: dict[str, dict[str, int]] = {
    "tunis":       {"firefighters": 8,  "ambulances": 10, "helicopters": 20},
    "nabeul":      {"firefighters": 15, "ambulances": 12, "helicopters": 35},
    "beja":        {"firefighters": 22, "ambulances": 18, "helicopters": 40},
    "ain_draham":  {"firefighters": 35, "ambulances": 30, "helicopters": 25},
    "tabarka":     {"firefighters": 28, "ambulances": 25, "helicopters": 30},
    "sfax":        {"firefighters": 12, "ambulances": 10, "helicopters": 28},
    "djerba":      {"firefighters": 20, "ambulances": 15, "helicopters": 45},
    "tozeur":      {"firefighters": 45, "ambulances": 40, "helicopters": 35},
    "tataouine":   {"firefighters": 55, "ambulances": 50, "helicopters": 40},
    "el_jem":      {"firefighters": 18, "ambulances": 15, "helicopters": 32},
    "bulla_regia": {"firefighters": 25, "ambulances": 22, "helicopters": 35},  # Rural, near Jendouba
    "dougga":      {"firefighters": 30, "ambulances": 28, "helicopters": 38},  # Rural, elevated/harder access
    "ichkeul":     {"firefighters": 20, "ambulances": 18, "helicopters": 30},  # Near Bizerte/Menzel Bourguiba
    "hammamet":    {"firefighters": 14, "ambulances": 12, "helicopters": 32},  # Well-connected coastal town
}


@dataclass
class ResourceAllocation:
    resource_type: str
    recommended_units: int
    reasoning: str
    estimated_response_min: int


@dataclass
class EmergencyPlan:
    zone_id: str
    zone_name: str
    overall_priority: str           # low/medium/high/critical
    priority_score: float           # 0-100 composite
    recommended_allocations: list[ResourceAllocation]
    intervention_sequence: list[str]
    estimated_containment_hours: float
    resources_required: dict
    xai_explanation: str
    is_simulated: bool
    updated_at: str


def _priority_from_score(s: float) -> str:
    if s >= 70:
        return "critical"
    if s >= 50:
        return "high"
    if s >= 30:
        return "medium"
    return "low"


def _compute_allocations(
    zone_id: str,
    fire_score: float,
    flood_score: float,
    water_score: float,
    electricity_score: float,
) -> list[ResourceAllocation]:
    allocations = []
    rt = BASE_RESPONSE_TIME.get(zone_id, {"firefighters": 30, "ambulances": 25, "helicopters": 40})

    # Firefighters — scale with fire risk
    if fire_score >= 30:
        units = max(2, int(fire_score / 20))
        allocations.append(ResourceAllocation(
            resource_type="Firefighter Teams",
            recommended_units=units,
            reasoning=f"Fire risk score {fire_score:.0f}/100 requires pre-positioned suppression capacity.",
            estimated_response_min=rt.get("firefighters", 30),
        ))

    # Water trucks — fire and drought
    if fire_score >= 40 or water_score >= 60:
        wt = max(2, int((fire_score + water_score) / 40))
        allocations.append(ResourceAllocation(
            resource_type="Water Trucks",
            recommended_units=wt,
            reasoning="Combined fire suppression and water distribution demand.",
            estimated_response_min=rt.get("firefighters", 30) + 10,
        ))

    # Ambulances — any high risk
    composite = max(fire_score, flood_score)
    if composite >= 40:
        ambs = max(1, int(composite / 30))
        allocations.append(ResourceAllocation(
            resource_type="Ambulances",
            recommended_units=ambs,
            reasoning=f"High hazard score ({composite:.0f}/100) increases likelihood of casualties.",
            estimated_response_min=rt.get("ambulances", 25),
        ))

    # Civil protection — flood or critical
    if flood_score >= 50:
        allocations.append(ResourceAllocation(
            resource_type="Civil Protection Teams",
            recommended_units=max(2, int(flood_score / 20)),
            reasoning=f"Flood probability {flood_score:.0f}% requires evacuation coordination.",
            estimated_response_min=35,
        ))

    # Helicopter — remote zones or critical fire
    if fire_score >= 70 or (flood_score >= 70 and zone_id in ("ain_draham", "beja", "tabarka", "bulla_regia")):
        allocations.append(ResourceAllocation(
            resource_type="Helicopter",
            recommended_units=1,
            reasoning="Critical risk with difficult ground access — aerial surveillance and evacuation required.",
            estimated_response_min=rt.get("helicopters", 35),
        ))

    # Police — any serious scenario
    if max(fire_score, flood_score) >= 50:
        allocations.append(ResourceAllocation(
            resource_type="Police Officers",
            recommended_units=max(4, int(max(fire_score, flood_score) / 15)),
            reasoning="Road management, perimeter control, and tourist safety coordination.",
            estimated_response_min=15,
        ))

    return allocations if allocations else [
        ResourceAllocation(
            resource_type="Monitoring Team",
            recommended_units=1,
            reasoning="Low risk — routine monitoring only.",
            estimated_response_min=30,
        )
    ]


def _intervention_sequence(fire_score: float, flood_score: float) -> list[str]:
    seq = []
    dominant = "fire" if fire_score >= flood_score else "flood"

    if dominant == "fire":
        seq = [
            "1. Deploy aerial surveillance helicopter for hotspot mapping.",
            "2. Position water trucks at forest access points.",
            "3. Pre-evacuate villages within 5 km of fire perimeter.",
            "4. Activate firebreak along main access roads.",
            "5. Coordinate with forestry service (ODESYPANO) for containment lines.",
            "6. Maintain ambulance standby at safe evacuation points.",
        ]
    else:
        seq = [
            "1. Activate flood warning system across affected municipalities.",
            "2. Deploy civil protection teams to low-lying evacuee collection points.",
            "3. Close flooded roads and redirect tourist traffic via high-ground alternates.",
            "4. Position ambulances at evacuation centres.",
            "5. Coordinate tanker distribution if water supply affected.",
            "6. Monitor oued (wadi) levels hourly until recession.",
        ]

    if max(fire_score, flood_score) < 30:
        seq = ["1. Monitor conditions with automated sensor network.", "2. No active deployment required."]
    return seq


def _containment_estimate(score: float, zone_id: str) -> float:
    """Rough estimate of hours to achieve containment based on risk score."""
    remote_bonus = 1.5 if zone_id in ("tataouine", "tozeur", "ain_draham", "bulla_regia", "dougga") else 1.0
    if score < 30:
        return 0.0
    if score < 50:
        return round(2.0 * remote_bonus, 1)
    if score < 70:
        return round(6.0 * remote_bonus, 1)
    return round(18.0 * remote_bonus, 1)


def _xai_explanation(zone_id: str, fire: float, flood: float, water: float, elec: float, score: float) -> str:
    dominant = max([(fire, "fire"), (flood, "flood"), (water, "water shortage"), (elec, "electricity outage")], key=lambda x: x[0])
    factors = []
    if fire >= 40:
        factors.append(f"active wildfire risk ({fire:.0f}/100)")
    if flood >= 40:
        factors.append(f"flood threat ({flood:.0f}/100)")
    if water >= 50:
        factors.append(f"water stress ({water:.0f}/100)")
    if elec >= 50:
        factors.append(f"electricity instability ({elec:.0f}/100)")
    if not factors:
        return f"Priority score {score:.0f}/100 — no significant hazard active. Routine monitoring recommended."
    return (
        f"Emergency priority score {score:.0f}/100. Primary hazard: {dominant[0]:.0f}/100 {dominant[1]}. "
        f"Contributing factors: {'; '.join(factors)}. "
        "Resource allocation optimised to address dominant hazard first."
    )


def compute_emergency_plan(
    zone_id: str,
    zone_name: str,
    fire_risk_score: float = 0.0,
    flood_risk_score: float = 0.0,
    water_risk_score: float = 0.0,
    electricity_risk_score: float = 0.0,
) -> EmergencyPlan:
    # Composite priority score — fire and flood weighted most heavily
    priority_score = (
        fire_risk_score  * 0.40 +
        flood_risk_score * 0.30 +
        water_risk_score * 0.15 +
        electricity_risk_score * 0.15
    )
    priority = _priority_from_score(priority_score)
    allocations = _compute_allocations(
        zone_id, fire_risk_score, flood_risk_score, water_risk_score, electricity_risk_score
    )
    sequence = _intervention_sequence(fire_risk_score, flood_risk_score)
    containment_h = _containment_estimate(priority_score, zone_id)

    resources_required = {a.resource_type: a.recommended_units for a in allocations}
    xai = _xai_explanation(zone_id, fire_risk_score, flood_risk_score, water_risk_score, electricity_risk_score, priority_score)

    return EmergencyPlan(
        zone_id=zone_id,
        zone_name=zone_name,
        overall_priority=priority,
        priority_score=round(priority_score, 1),
        recommended_allocations=allocations,
        intervention_sequence=sequence,
        estimated_containment_hours=containment_h,
        resources_required=resources_required,
        xai_explanation=xai,
        is_simulated=True,
        updated_at=datetime.now(timezone.utc).isoformat(),
    )
