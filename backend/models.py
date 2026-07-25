from datetime import datetime
from typing import Any

from pydantic import BaseModel


# ─── Existing Models ──────────────────────────────────────────────────────────

class Zone(BaseModel):
    id: str
    name: str
    lat: float
    lon: float
    type: str
    neighbors: list[str]


class RiskFactors(BaseModel):
    temperature_c: float
    wind_kmh: float
    humidity_pct: float
    rain_mm: float
    active_fires_nearby: int
    ndvi: float


class MLPrediction(BaseModel):
    prediction: str                 # "fire" | "not_fire"
    fire_probability: float         # 0.0-1.0, raw model output
    confidence: float               # max(p, 1-p)
    explanation: str                # data-driven, from training-set feature stats
    model_version: str              # trained_at timestamp of the loaded model
    dataset_source: str


class SourceDatasets(BaseModel):
    weather: str
    fires: str
    ndvi: str
    ml_model: str


class ZonePredictionResponse(BaseModel):
    zone_id: str
    zone_name: str
    risk_score: int
    risk_level: str
    ml: MLPrediction | None         # None if the model isn't trained/available
    input_features: RiskFactors
    source_datasets: SourceDatasets
    timestamp: datetime


class ZoneRisk(BaseModel):
    zone_id: str
    zone_name: str
    lat: float
    lon: float
    risk_score: int
    risk_level: str
    factors: RiskFactors
    updated_at: datetime


class TouristQuery(BaseModel):
    zone_id: str
    visit_date: str
    lang: str = "fr"  # "fr" or "en"


class TouristResponse(BaseModel):
    zone_id: str
    zone_name: str
    risk_score: int
    safe: bool
    explanation: str
    alternative_zone_id: str | None
    alternative_zone_name: str | None
    xp_awarded: int
    forecast_used: bool
    effective_date: str


class ForecastDay(BaseModel):
    date: str
    risk_score: int
    risk_level: str
    temperature_c: float
    humidity_pct: float
    wind_kmh: float
    rain_mm: float
    fire_probability: float | None


class ZoneForecastResponse(BaseModel):
    zone_id: str
    zone_name: str
    forecast_available: bool
    days: list[ForecastDay]
    note: str


class NdviZoneStatus(BaseModel):
    zone_id: str
    is_real: bool
    composite_date: str | None = None


class NdviStatus(BaseModel):
    real_cache_available: bool
    fetched_at: str | None
    zones: list[NdviZoneStatus]
    earthdata_credentials_configured: bool


class ScenarioOverride(BaseModel):
    zone_id: str
    ndvi: float | None = None
    temperature_c: float | None = None
    wind_kmh: float | None = None
    humidity_pct: float | None = None
    rain_mm: float | None = None
    active_fires_nearby: int | None = None


# ─── New Multi-Agent Models ───────────────────────────────────────────────────

class FloodFactorsModel(BaseModel):
    rainfall_mm: float
    soil_saturation_pct: float
    drainage_index: float
    historical_freq: float
    terrain_class: str


class FloodRiskResponse(BaseModel):
    zone_id: str
    zone_name: str
    flood_probability: float
    risk_level: str
    flooded_roads: list[str]
    hotels_at_risk: int
    evacuation_recommendations: list[str]
    factors: FloodFactorsModel
    xai_explanation: str
    is_simulated: bool
    updated_at: str


class WaterFactorsModel(BaseModel):
    reservoir_level_pct: float
    tourism_demand_multiplier: float
    leak_index: float
    temperature_c: float
    estimated_daily_consumption_m3: float


class WaterRiskResponse(BaseModel):
    zone_id: str
    zone_name: str
    shortage_probability: float
    risk_level: str
    regions_under_stress: list[str]
    conservation_recommendations: list[str]
    factors: WaterFactorsModel
    xai_explanation: str
    is_simulated: bool
    updated_at: str


class ElectricityFactorsModel(BaseModel):
    grid_reliability: float
    hotel_backup_pct: float
    solar_index: float
    active_outage: bool
    peak_load_factor: float


class ElectricityRiskResponse(BaseModel):
    zone_id: str
    zone_name: str
    outage_probability: float
    risk_level: str
    active_outage: bool
    outage_affected_area: str | None
    estimated_recovery_hours: int | None
    resilient_tourism_zones: list[str]
    hotel_availability_pct: float
    xai_explanation: str
    is_simulated: bool
    updated_at: str


class TourismRecommendationResponse(BaseModel):
    zone_id: str
    zone_name: str
    overall_safety_score: float
    recommended_destinations: list[dict]
    active_festivals: list[dict]
    smart_routing: list[dict]
    tourist_density: str
    accessibility: dict
    hazard_summary: dict
    top_recommendation: str
    is_simulated: bool
    updated_at: str


class ResourceAllocationModel(BaseModel):
    resource_type: str
    recommended_units: int
    reasoning: str
    estimated_response_min: int


class EmergencyPlanResponse(BaseModel):
    zone_id: str
    zone_name: str
    overall_priority: str
    priority_score: float
    recommended_allocations: list[ResourceAllocationModel]
    intervention_sequence: list[str]
    estimated_containment_hours: float
    resources_required: dict
    xai_explanation: str
    is_simulated: bool
    updated_at: str


class XAIFactorBreakdown(BaseModel):
    factor: str
    value: str
    contribution: str
    direction: str
    threshold: str | None = None


class XAIExplanationResponse(BaseModel):
    agent: str
    zone_id: str
    zone_name: str
    prediction: str
    risk_level: str
    risk_score: float
    factors_breakdown: list[dict]
    historical_context: str
    plain_language: str
    confidence_note: str
    updated_at: str


class NotificationModel(BaseModel):
    id: str
    stakeholder: str
    severity: str
    icon: str
    title: str
    message: str
    actions: list[str]
    zone_id: str
    zone_name: str
    agent_source: str
    timestamp: str


class AgentStatusCard(BaseModel):
    agent_name: str
    agent_key: str
    icon: str
    risk_level: str
    risk_score: float
    status_label: str
    key_metric: str
    is_simulated: bool


class TouristDashboardResponse(BaseModel):
    zone_id: str
    zone_name: str
    overall_safety_score: float
    agent_cards: list[AgentStatusCard]
    fire: dict
    flood: dict
    water: dict
    electricity: dict
    tourism: dict
    emergency: dict
    notifications: list[dict]
    updated_at: str


# ─── Hotel Resilience ──────────────────────────────────────────────────────────

class HotelDeclaration(BaseModel):
    zone_id: str
    hotel_name: str
    electricity_available: bool = True
    water_available: bool = True
    internet_available: bool = True
    generator_available: bool = False
    battery_backup: bool = False
    solar_panels: bool = False
    remaining_autonomy_hours: float | None = None
    rooms_available: int | None = None
    contact_email: str | None = None


class HotelStatus(HotelDeclaration):
    id: int
    updated_at: str


class ZoneResilienceSummary(BaseModel):
    zone_id: str
    zone_name: str
    hotel_count: int
    operational_pct: float
    generator_coverage_pct: float
    battery_coverage_pct: float
    solar_coverage_pct: float
    rooms_available: int


class HotelResilienceStats(BaseModel):
    total_hotels: int
    operational_pct: float
    generator_coverage_pct: float
    battery_coverage_pct: float
    solar_coverage_pct: float
    rooms_available_in_safe_zones: int
    zones: list[ZoneResilienceSummary]
    most_resilient_zone_id: str | None
    most_resilient_zone_name: str | None


class HotelAlternative(BaseModel):
    hotel_name: str
    zone_id: str
    zone_name: str
    rooms_available: int | None


class HotelAlternativeResponse(BaseModel):
    requested_hotel: str
    zone_id: str
    found: bool
    is_operational: bool | None
    alternatives: list[HotelAlternative]
    reason: str


# ─── Smart Route Planner ───────────────────────────────────────────────────────

class RoutePoint(BaseModel):
    id: str
    name: str


class RouteHazard(BaseModel):
    zone_name: str
    risk_level: str
    distance_km: float


class RouteOption(BaseModel):
    duration_min: float
    distance_km: float
    geometry: dict          # GeoJSON LineString, as returned by OSRM
    hazards: list[RouteHazard]


class RoutePlanResponse(BaseModel):
    origin: RoutePoint
    destination: RoutePoint
    has_alternative: bool
    chose_alternative: bool
    default_route: RouteOption
    recommended_route: RouteOption
    extra_minutes: float
    hazards_avoided: list[RouteHazard]


# ─── AI Tourist Guide Chat ──────────────────────────────────────────────────

class ChatMessage(BaseModel):
    role: str  # "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    lang: str = "fr"  # "fr" | "en" | "ar"


class ChatResponse(BaseModel):
    reply: str
    used_llm: bool
    lang: str
