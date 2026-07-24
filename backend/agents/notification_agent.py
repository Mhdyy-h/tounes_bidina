"""
Intelligent Notification Agent
================================
Continuously monitors all hazard levels and generates structured notifications
for the appropriate stakeholders when danger is detected.

Stakeholder types:
- tourists:          mobile alerts about nearby hazards
- hotels:            operational alerts (evacuation, water, electricity)
- civil_protection:  emergency deployment requests
- municipalities:    administrative recommendations

Each notification has severity, message, and recommended actions.
"""

from dataclasses import dataclass
from datetime import datetime, timezone


SEVERITY_THRESHOLDS = {
    "low":      {"fire": 60, "flood": 50, "water": 60, "electricity": 60},
    "moderate": {"fire": 40, "flood": 35, "water": 45, "electricity": 45},
    "watch":    {"fire": 25, "flood": 20, "water": 30, "electricity": 30},
}


@dataclass
class Notification:
    id: str
    stakeholder: str          # tourist | hotel | civil_protection | municipality
    severity: str             # info | watch | warning | critical
    icon: str
    title: str
    message: str
    actions: list[str]
    zone_id: str
    zone_name: str
    agent_source: str         # which agent generated this
    timestamp: str


def _notification_id(zone_id: str, agent: str, stakeholder: str) -> str:
    ts = datetime.now(timezone.utc).strftime("%H%M%S")
    return f"{zone_id}_{agent}_{stakeholder}_{ts}"


def _fire_notifications(zone_id: str, zone_name: str, score: float) -> list[Notification]:
    notifs = []
    ts = datetime.now(timezone.utc).isoformat()

    if score >= 70:
        notifs.append(Notification(
            id=_notification_id(zone_id, "fire", "tourist"),
            stakeholder="tourist",
            severity="critical",
            icon="🔥",
            title=f"Wildfire Alert — {zone_name}",
            message=f"Active wildfire risk (score {score:.0f}/100) within {zone_name}. Avoid forest areas and roads marked as blocked.",
            actions=["Do not enter marked fire zones", "Follow evacuation signs", "Call 197 (civil protection) if in danger"],
            zone_id=zone_id,
            zone_name=zone_name,
            agent_source="Fire Intelligence Agent",
            timestamp=ts,
        ))
        notifs.append(Notification(
            id=_notification_id(zone_id, "fire", "hotel"),
            stakeholder="hotel",
            severity="critical",
            icon="🔥",
            title=f"⚠ Wildfire predicted within 7 km — {zone_name}",
            message=f"Fire probability at {score:.0f}/100. Prepare evacuation protocol immediately.",
            actions=["Activate hotel evacuation plan", "Close outdoor facilities", "Redirect tourist buses to safe routes", "Notify guests of alternative itineraries"],
            zone_id=zone_id,
            zone_name=zone_name,
            agent_source="Fire Intelligence Agent",
            timestamp=ts,
        ))
        notifs.append(Notification(
            id=_notification_id(zone_id, "fire", "civil_protection"),
            stakeholder="civil_protection",
            severity="critical",
            icon="🚨",
            title=f"DEPLOY: Fire Emergency — {zone_name}",
            message=f"Fire Intelligence Agent reports {score:.0f}/100 wildfire probability. Immediate deployment recommended.",
            actions=["Deploy firefighter teams as per emergency plan", "Position water trucks at forest access points", "Activate helicopter surveillance", "Establish incident command post"],
            zone_id=zone_id,
            zone_name=zone_name,
            agent_source="Fire Intelligence Agent",
            timestamp=ts,
        ))

    elif score >= 50:
        notifs.append(Notification(
            id=_notification_id(zone_id, "fire", "tourist"),
            stakeholder="tourist",
            severity="warning",
            icon="⚠️",
            title=f"Fire Watch — {zone_name}",
            message=f"Elevated wildfire risk ({score:.0f}/100) in {zone_name}. Hiking trails may close at short notice.",
            actions=["Avoid barbecues and open flames", "Stay on marked paths", "Monitor local alerts"],
            zone_id=zone_id,
            zone_name=zone_name,
            agent_source="Fire Intelligence Agent",
            timestamp=ts,
        ))

    elif score >= 30:
        notifs.append(Notification(
            id=_notification_id(zone_id, "fire", "tourist"),
            stakeholder="tourist",
            severity="watch",
            icon="🟡",
            title=f"Fire Conditions Watch — {zone_name}",
            message=f"Dry and warm conditions ({score:.0f}/100). Normal access maintained but remain vigilant.",
            actions=["No open flames in forest areas", "Report smoke to 197"],
            zone_id=zone_id,
            zone_name=zone_name,
            agent_source="Fire Intelligence Agent",
            timestamp=ts,
        ))

    return notifs


def _flood_notifications(zone_id: str, zone_name: str, score: float) -> list[Notification]:
    notifs = []
    ts = datetime.now(timezone.utc).isoformat()

    if score >= 60:
        notifs.append(Notification(
            id=_notification_id(zone_id, "flood", "tourist"),
            stakeholder="tourist",
            severity="critical",
            icon="🌊",
            title=f"Flood Alert — {zone_name}",
            message=f"Flood probability {score:.0f}/100. Road closures possible. Check route before travel.",
            actions=["Avoid valley roads and underpasses", "Do not cross flooded roads", "Use alternative routes as directed"],
            zone_id=zone_id,
            zone_name=zone_name,
            agent_source="Flood Intelligence Agent",
            timestamp=ts,
        ))
        notifs.append(Notification(
            id=_notification_id(zone_id, "flood", "municipality"),
            stakeholder="municipality",
            severity="critical",
            icon="🌊",
            title=f"Flood Risk — Action Required — {zone_name}",
            message=f"Flood probability at {score:.0f}/100. Activate municipal flood response protocol.",
            actions=["Open designated flood shelters", "Deploy civil protection teams", "Issue public warnings via radio and SMS", "Coordinate with ONAS drainage management"],
            zone_id=zone_id,
            zone_name=zone_name,
            agent_source="Flood Intelligence Agent",
            timestamp=ts,
        ))

    elif score >= 35:
        notifs.append(Notification(
            id=_notification_id(zone_id, "flood", "tourist"),
            stakeholder="tourist",
            severity="warning",
            icon="⚠️",
            title=f"Flood Watch — {zone_name}",
            message=f"Elevated flood risk ({score:.0f}/100). Some roads may be affected.",
            actions=["Check road conditions before departure", "Avoid dry riverbeds (oueds)"],
            zone_id=zone_id,
            zone_name=zone_name,
            agent_source="Flood Intelligence Agent",
            timestamp=ts,
        ))

    return notifs


def _water_notifications(zone_id: str, zone_name: str, score: float) -> list[Notification]:
    notifs = []
    ts = datetime.now(timezone.utc).isoformat()

    if score >= 65:
        notifs.append(Notification(
            id=_notification_id(zone_id, "water", "hotel"),
            stakeholder="hotel",
            severity="warning",
            icon="💧",
            title=f"Water Shortage Risk — {zone_name}",
            message=f"Water shortage probability at {score:.0f}/100. Hotel consumption protocols should be activated.",
            actions=["Activate water-saving protocol", "Fill emergency water reserves", "Limit pool refilling and laundry cycles", "Brief guests on conservation measures"],
            zone_id=zone_id,
            zone_name=zone_name,
            agent_source="Water Resource Agent",
            timestamp=ts,
        ))
        notifs.append(Notification(
            id=_notification_id(zone_id, "water", "tourist"),
            stakeholder="tourist",
            severity="info",
            icon="💧",
            title=f"Water Conservation in Effect — {zone_name}",
            message=f"Water stress conditions ({score:.0f}/100). Please conserve water during your stay.",
            actions=["Reuse hotel towels and linen", "Report dripping taps to hotel reception", "Use bottled water for drinking"],
            zone_id=zone_id,
            zone_name=zone_name,
            agent_source="Water Resource Agent",
            timestamp=ts,
        ))

    return notifs


def _electricity_notifications(zone_id: str, zone_name: str, score: float, active_outage: bool = False) -> list[Notification]:
    notifs = []
    ts = datetime.now(timezone.utc).isoformat()

    if active_outage:
        notifs.append(Notification(
            id=_notification_id(zone_id, "electricity", "tourist"),
            stakeholder="tourist",
            severity="warning",
            icon="⚡",
            title=f"Power Outage Active — {zone_name}",
            message=f"Electricity outage currently active in part of {zone_name}. Some facilities may be affected.",
            actions=["Most hotels have backup generators — check with reception", "Charge devices when power is available", "Avoid using lifts during outage"],
            zone_id=zone_id,
            zone_name=zone_name,
            agent_source="Electricity & Infrastructure Agent",
            timestamp=ts,
        ))
    elif score >= 50:
        notifs.append(Notification(
            id=_notification_id(zone_id, "electricity", "hotel"),
            stakeholder="hotel",
            severity="watch",
            icon="⚡",
            title=f"Grid Stress Warning — {zone_name}",
            message=f"Electricity instability risk at {score:.0f}/100. Verify generator readiness.",
            actions=["Test backup generator", "Ensure fuel reserves are full", "Configure automatic failover"],
            zone_id=zone_id,
            zone_name=zone_name,
            agent_source="Electricity & Infrastructure Agent",
            timestamp=ts,
        ))

    return notifs


def generate_notifications(
    zone_id: str,
    zone_name: str,
    fire_score: float = 0.0,
    flood_score: float = 0.0,
    water_score: float = 0.0,
    electricity_score: float = 0.0,
    electricity_active_outage: bool = False,
) -> list[Notification]:
    """Generate all relevant notifications for a zone based on current agent scores."""
    notifications = []
    notifications.extend(_fire_notifications(zone_id, zone_name, fire_score))
    notifications.extend(_flood_notifications(zone_id, zone_name, flood_score))
    notifications.extend(_water_notifications(zone_id, zone_name, water_score))
    notifications.extend(_electricity_notifications(zone_id, zone_name, electricity_score, electricity_active_outage))
    return notifications
