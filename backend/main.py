import asyncio
import json
import logging
import os
from dataclasses import asdict
from datetime import date, datetime, timezone
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from backend import scenario
from backend.agents.flood_agent import compute_flood_risk
from backend.agents.water_agent import compute_water_risk
from backend.agents.electricity_agent import compute_electricity_risk
from backend.agents.tourism_agent import compute_tourism_recommendation
from backend.agents.emergency_agent import compute_emergency_plan
from backend.agents.xai_agent import generate_xai
from backend.agents.notification_agent import generate_notifications
from backend import db
from backend import email_client
from backend.famma_dhaw_client import get_zone_outage_status
from backend.firms_client import get_active_fires
from backend.chat_agent import chat_reply
from backend.hotel_service import compute_resilience_stats, find_hotel_alternative
from backend.llm_agent import explain_and_recommend
from backend.ml_risk import compute_composite_risk, source_datasets_descriptor
from backend.models import (
    AgentStatusCard,
    ChatRequest,
    ChatResponse,
    ElectricityRiskResponse,
    EmergencyPlanResponse,
    FloodRiskResponse,
    ForecastDay,
    HotelAlternativeResponse,
    HotelDeclaration,
    HotelResilienceStats,
    HotelStatus,
    MLPrediction,
    NdviStatus,
    NdviZoneStatus,
    NotificationModel,
    RiskFactors,
    RoutePlanResponse,
    ScenarioOverride,
    SourceDatasets,
    TouristDashboardResponse,
    TouristQuery,
    TouristResponse,
    TourismRecommendationResponse,
    WaterRiskResponse,
    XAIExplanationResponse,
    Zone,
    ZoneForecastResponse,
    ZonePredictionResponse,
    ZoneRisk,
)
from backend.ndvi_cache import load_real_cache, refresh_real_ndvi
from backend.risk_forecast import compute_forecast
from backend.route_planner import AIRPORTS, plan_route
from backend.weather_client import get_forecast, get_weather

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
FRONTEND_DIR = BASE_DIR / "frontend"

app = FastAPI(title="Tunisia Guardian AI — Multi-Agent Platform")


@app.on_event("startup")
async def _startup():
    db.init_db()


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def no_cache_static(request, call_next):
    """Hackathon dev app — static JS/CSS must never be served stale mid-demo."""
    response = await call_next(request)
    if request.url.path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return response


app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


# ─── Utility helpers ──────────────────────────────────────────────────────────

def _load_zones() -> list[Zone]:
    with open(DATA_DIR / "zones.json", encoding="utf-8") as f:
        raw = json.load(f)
    return [Zone(**z) for z in raw]


def _zones_by_id() -> dict[str, Zone]:
    return {z.id: z for z in _load_zones()}


async def _gather_factors(zone: Zone, ndvi_values: dict[str, float]) -> tuple[RiskFactors, dict]:
    """Returns (factors, source_info). source_info labels each factor as live/overridden/fallback."""
    weather, (active_fires, fires_is_live) = await asyncio.gather(
        get_weather(zone.lat, zone.lon), get_active_fires(zone.lat, zone.lon)
    )

    overrides = scenario.get_factor_overrides(zone.id)

    factors = RiskFactors(
        temperature_c=overrides.get("temperature_c", weather["temperature_c"]),
        wind_kmh=overrides.get("wind_kmh", weather["wind_kmh"]),
        humidity_pct=overrides.get("humidity_pct", weather["humidity_pct"]),
        rain_mm=overrides.get("rain_mm", weather["rain_mm"]),
        active_fires_nearby=overrides.get("active_fires_nearby", active_fires),
        ndvi=overrides.get("ndvi", ndvi_values.get(zone.id, 0.55)),
    )

    weather_overridden = any(
        k in overrides for k in ("temperature_c", "wind_kmh", "humidity_pct", "rain_mm")
    )
    fires_overridden = "active_fires_nearby" in overrides
    ndvi_overridden = "ndvi" in overrides

    source_info = {
        "weather_is_live": weather["is_live"] and not weather_overridden,
        "weather_overridden": weather_overridden,
        "fires_is_live": fires_is_live and not fires_overridden,
        "fires_overridden": fires_overridden,
        "ndvi_source": scenario.ndvi_source_for_zone(zone.id),
        "ndvi_overridden": ndvi_overridden,
    }

    return factors, source_info


async def _compute_zone_risk(zone: Zone, ndvi_values: dict[str, float]) -> ZoneRisk:
    factors, _ = await _gather_factors(zone, ndvi_values)
    score, level, _ = compute_composite_risk(factors)

    return ZoneRisk(
        zone_id=zone.id,
        zone_name=zone.name,
        lat=zone.lat,
        lon=zone.lon,
        risk_score=score,
        risk_level=level,
        factors=factors,
        updated_at=datetime.now(timezone.utc),
    )


MAX_RELIABLE_FORECAST_DAYS = 3


async def _resolve_zone_risk_for_date(
    zone: Zone, ndvi_values: dict[str, float], days_ahead: int
) -> tuple[ZoneRisk, bool]:
    if days_ahead <= 0 or days_ahead > MAX_RELIABLE_FORECAST_DAYS:
        return await _compute_zone_risk(zone, ndvi_values), False

    overrides = scenario.get_factor_overrides(zone.id)
    forecast_days, (active_fires, _) = await asyncio.gather(
        get_forecast(zone.lat, zone.lon, days=MAX_RELIABLE_FORECAST_DAYS),
        get_active_fires(zone.lat, zone.lon),
    )
    if forecast_days is None or days_ahead > len(forecast_days):
        return await _compute_zone_risk(zone, ndvi_values), False

    day = forecast_days[days_ahead - 1]
    factors = RiskFactors(
        temperature_c=overrides.get("temperature_c", day["temperature_c"]),
        wind_kmh=overrides.get("wind_kmh", day["wind_kmh"]),
        humidity_pct=overrides.get("humidity_pct", day["humidity_pct"]),
        rain_mm=overrides.get("rain_mm", day["rain_mm"]),
        active_fires_nearby=overrides.get("active_fires_nearby", active_fires),
        ndvi=overrides.get("ndvi", ndvi_values.get(zone.id, 0.55)),
    )
    score, level, _ = compute_composite_risk(factors)
    risk = ZoneRisk(
        zone_id=zone.id,
        zone_name=zone.name,
        lat=zone.lat,
        lon=zone.lon,
        risk_score=score,
        risk_level=level,
        factors=factors,
        updated_at=datetime.now(timezone.utc),
    )
    return risk, True


# ─── Page Routes ──────────────────────────────────────────────────────────────

@app.get("/")
async def serve_index():
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/tourist")
async def serve_tourist():
    return FileResponse(FRONTEND_DIR / "tourist.html")


@app.get("/tourist-portal")
async def serve_tourist_portal():
    return FileResponse(FRONTEND_DIR / "tourist_portal.html")


@app.get("/dashboard")
async def serve_dashboard():
    return FileResponse(FRONTEND_DIR / "dashboard.html")


@app.get("/hotel-portal")
async def serve_hotel_portal():
    return FileResponse(FRONTEND_DIR / "hotel_portal.html")


# ─── Existing Risk API ────────────────────────────────────────────────────────

@app.get("/api/zones", response_model=list[Zone])
async def api_zones():
    return _load_zones()


async def _compute_all_risks() -> list[ZoneRisk]:
    zones = _load_zones()
    ndvi_values = scenario.read_ndvi()
    return list(await asyncio.gather(*(_compute_zone_risk(z, ndvi_values) for z in zones)))


@app.get("/api/risk", response_model=list[ZoneRisk])
async def api_risk():
    return await _compute_all_risks()


@app.get("/api/risk/stream")
async def api_risk_stream():
    """Server-Sent Events: pushes the full risk list every few seconds."""
    async def event_generator():
        try:
            while True:
                risks = await _compute_all_risks()
                payload = json.dumps([r.model_dump(mode="json") for r in risks])
                yield f"data: {payload}\n\n"
                await asyncio.sleep(5)
        except asyncio.CancelledError:
            pass

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/risk/{zone_id}", response_model=ZoneRisk)
async def api_risk_zone(zone_id: str):
    zones_by_id = _zones_by_id()
    zone = zones_by_id.get(zone_id)
    if zone is None:
        raise HTTPException(status_code=404, detail=f"Unknown zone_id: {zone_id}")
    ndvi_values = scenario.read_ndvi()
    return await _compute_zone_risk(zone, ndvi_values)


@app.get("/api/predict/{zone_id}", response_model=ZonePredictionResponse)
async def api_predict_zone(zone_id: str):
    zones_by_id = _zones_by_id()
    zone = zones_by_id.get(zone_id)
    if zone is None:
        raise HTTPException(status_code=404, detail=f"Unknown zone_id: {zone_id}")

    ndvi_values = scenario.read_ndvi()
    factors, source_info = await _gather_factors(zone, ndvi_values)
    score, level, ml_result = compute_composite_risk(factors)

    return ZonePredictionResponse(
        zone_id=zone.id,
        zone_name=zone.name,
        risk_score=score,
        risk_level=level,
        ml=MLPrediction(**ml_result) if ml_result else None,
        input_features=factors,
        source_datasets=SourceDatasets(**source_datasets_descriptor(source_info)),
        timestamp=datetime.now(timezone.utc),
    )


@app.get("/api/forecast/{zone_id}", response_model=ZoneForecastResponse)
async def api_forecast_zone(zone_id: str, days: int = 3):
    zones_by_id = _zones_by_id()
    zone = zones_by_id.get(zone_id)
    if zone is None:
        raise HTTPException(status_code=404, detail=f"Unknown zone_id: {zone_id}")

    ndvi_values = scenario.read_ndvi()
    overrides = scenario.get_factor_overrides(zone.id)
    ndvi = overrides.get("ndvi", ndvi_values.get(zone.id, 0.55))
    active_fires, _ = await get_active_fires(zone.lat, zone.lon)
    active_fires = overrides.get("active_fires_nearby", active_fires)

    days_data = await compute_forecast(zone.lat, zone.lon, ndvi, active_fires, days=days)

    if days_data is None:
        return ZoneForecastResponse(
            zone_id=zone.id,
            zone_name=zone.name,
            forecast_available=False,
            days=[],
            note="Weather forecast unavailable — retry later.",
        )

    return ZoneForecastResponse(
        zone_id=zone.id,
        zone_name=zone.name,
        forecast_available=True,
        days=[ForecastDay(**d) for d in days_data],
        note="NDVI and active fires held at today's values (not forecastable); weather is a real Open-Meteo D+1/D+2/D+3 forecast.",
    )


@app.post("/api/tourist/query", response_model=TouristResponse)
async def api_tourist_query(query: TouristQuery):
    zones_by_id = _zones_by_id()
    zone = zones_by_id.get(query.zone_id)
    if zone is None:
        raise HTTPException(status_code=404, detail=f"Unknown zone_id: {query.zone_id}")

    today = datetime.now(timezone.utc).date()
    try:
        visit_date = date.fromisoformat(query.visit_date)
        days_ahead = (visit_date - today).days
    except ValueError:
        visit_date = today
        days_ahead = 0

    ndvi_values = scenario.read_ndvi()
    neighbor_zones = [zones_by_id[n] for n in zone.neighbors if n in zones_by_id]
    results = await asyncio.gather(
        _resolve_zone_risk_for_date(zone, ndvi_values, days_ahead),
        *(_resolve_zone_risk_for_date(z, ndvi_values, days_ahead) for z in neighbor_zones),
    )
    (risk, forecast_used), *candidate_pairs = results
    candidate_zones = [r for r, _ in candidate_pairs]

    lang = query.lang if query.lang in ("fr", "en") else "fr"
    effective_date = visit_date if (forecast_used or days_ahead <= 0) else today
    if lang == "en":
        if forecast_used:
            date_context = f"real forecast for {effective_date.isoformat()} (in {days_ahead} day(s))"
        elif days_ahead > 0:
            date_context = (
                f"current conditions ({today.isoformat()}) - no reliable forecast beyond a few "
                f"days for {visit_date.isoformat()}"
            )
        else:
            date_context = f"current conditions ({today.isoformat()})"
    else:
        if forecast_used:
            date_context = f"prévision réelle pour le {effective_date.isoformat()} (dans {days_ahead} jour(s))"
        elif days_ahead > 0:
            date_context = (
                f"conditions actuelles ({today.isoformat()}) - pas de prévision fiable au-delà de "
                f"quelques jours pour le {visit_date.isoformat()}"
            )
        else:
            date_context = f"conditions actuelles ({today.isoformat()})"

    explanation, alternative_zone_id = await explain_and_recommend(
        zone.model_dump(), risk, candidate_zones, date_context, lang
    )

    alternative_zone_name = None
    if alternative_zone_id and alternative_zone_id in zones_by_id:
        alternative_zone_name = zones_by_id[alternative_zone_id].name

    return TouristResponse(
        zone_id=zone.id,
        zone_name=zone.name,
        risk_score=risk.risk_score,
        safe=risk.risk_score < 50,
        explanation=explanation,
        alternative_zone_id=alternative_zone_id,
        alternative_zone_name=alternative_zone_name,
        xp_awarded=10,
        forecast_used=forecast_used,
        effective_date=effective_date.isoformat(),
    )


# ─── New Multi-Agent Endpoints ────────────────────────────────────────────────

async def _get_zone_weather_simple(zone: Zone) -> dict:
    """Lightweight weather fetch — returns temperature and rainfall for non-fire agents."""
    try:
        weather = await get_weather(zone.lat, zone.lon)
        return {
            "temperature_c": weather.get("temperature_c", 28.0),
            "rain_mm": weather.get("rain_mm", 0.0),
            "humidity_pct": weather.get("humidity_pct", 55.0),
        }
    except Exception:
        return {"temperature_c": 28.0, "rain_mm": 0.0, "humidity_pct": 55.0}


@app.get("/api/agents/flood/{zone_id}")
async def api_flood_agent(zone_id: str):
    """Flood Intelligence Agent — probability, flooded roads, evacuation recommendations."""
    zones_by_id = _zones_by_id()
    zone = zones_by_id.get(zone_id)
    if zone is None:
        raise HTTPException(status_code=404, detail=f"Unknown zone_id: {zone_id}")
    wx = await _get_zone_weather_simple(zone)
    result = compute_flood_risk(
        zone_id=zone.id,
        zone_name=zone.name,
        rainfall_mm=wx["rain_mm"],
        humidity_pct=wx["humidity_pct"],
    )
    return asdict(result)


@app.get("/api/agents/water/{zone_id}")
async def api_water_agent(zone_id: str):
    """Water Resource Agent — shortage probability, stressed regions, conservation tips."""
    zones_by_id = _zones_by_id()
    zone = zones_by_id.get(zone_id)
    if zone is None:
        raise HTTPException(status_code=404, detail=f"Unknown zone_id: {zone_id}")
    wx = await _get_zone_weather_simple(zone)
    result = compute_water_risk(
        zone_id=zone.id,
        zone_name=zone.name,
        temperature_c=wx["temperature_c"],
    )
    return asdict(result)


@app.get("/api/agents/electricity/{zone_id}")
async def api_electricity_agent(zone_id: str):
    """Electricity & Infrastructure Agent — outage probability, resilient zones, hotel availability."""
    zones_by_id = _zones_by_id()
    zone = zones_by_id.get(zone_id)
    if zone is None:
        raise HTTPException(status_code=404, detail=f"Unknown zone_id: {zone_id}")
    wx, real_outage = await asyncio.gather(
        _get_zone_weather_simple(zone), get_zone_outage_status(zone.id)
    )
    result = compute_electricity_risk(
        zone_id=zone.id,
        zone_name=zone.name,
        temperature_c=wx["temperature_c"],
        real_outage=real_outage,
    )
    return asdict(result)


@app.get("/api/agents/tourism/{zone_id}")
async def api_tourism_agent(zone_id: str):
    """Tourism Intelligence Agent — safe destinations, smart routing, festivals."""
    zones_by_id = _zones_by_id()
    zone = zones_by_id.get(zone_id)
    if zone is None:
        raise HTTPException(status_code=404, detail=f"Unknown zone_id: {zone_id}")

    ndvi_values = scenario.read_ndvi()
    fire_risk_obj = await _compute_zone_risk(zone, ndvi_values)
    wx = await _get_zone_weather_simple(zone)

    flood = compute_flood_risk(zone.id, zone.name, wx["rain_mm"], wx["humidity_pct"])
    water = compute_water_risk(zone.id, zone.name, wx["temperature_c"])
    real_outage = await get_zone_outage_status(zone.id)
    elec = compute_electricity_risk(zone.id, zone.name, wx["temperature_c"], real_outage=real_outage)

    result = compute_tourism_recommendation(
        zone_id=zone.id,
        zone_name=zone.name,
        fire_risk_score=float(fire_risk_obj.risk_score),
        flood_risk_score=flood.flood_probability,
        water_risk_score=water.shortage_probability,
        electricity_risk_score=elec.outage_probability,
    )
    return asdict(result)


@app.get("/api/agents/emergency/{zone_id}")
async def api_emergency_agent(zone_id: str):
    """Emergency Optimization Agent — resource allocation, intervention sequence."""
    zones_by_id = _zones_by_id()
    zone = zones_by_id.get(zone_id)
    if zone is None:
        raise HTTPException(status_code=404, detail=f"Unknown zone_id: {zone_id}")

    ndvi_values = scenario.read_ndvi()
    fire_risk_obj = await _compute_zone_risk(zone, ndvi_values)
    wx = await _get_zone_weather_simple(zone)

    flood = compute_flood_risk(zone.id, zone.name, wx["rain_mm"], wx["humidity_pct"])
    water = compute_water_risk(zone.id, zone.name, wx["temperature_c"])
    real_outage = await get_zone_outage_status(zone.id)
    elec = compute_electricity_risk(zone.id, zone.name, wx["temperature_c"], real_outage=real_outage)

    result = compute_emergency_plan(
        zone_id=zone.id,
        zone_name=zone.name,
        fire_risk_score=float(fire_risk_obj.risk_score),
        flood_risk_score=flood.flood_probability,
        water_risk_score=water.shortage_probability,
        electricity_risk_score=elec.outage_probability,
    )
    return asdict(result)


@app.get("/api/agents/xai/{agent_type}/{zone_id}")
async def api_xai_agent(agent_type: str, zone_id: str):
    """XAI Agent — factor-by-factor explanation for any domain agent prediction."""
    valid_types = ("fire", "flood", "water", "electricity")
    if agent_type not in valid_types:
        raise HTTPException(status_code=400, detail=f"agent_type must be one of {valid_types}")

    zones_by_id = _zones_by_id()
    zone = zones_by_id.get(zone_id)
    if zone is None:
        raise HTTPException(status_code=404, detail=f"Unknown zone_id: {zone_id}")

    ndvi_values = scenario.read_ndvi()
    wx = await _get_zone_weather_simple(zone)

    if agent_type == "fire":
        fire_risk_obj = await _compute_zone_risk(zone, ndvi_values)
        factors = fire_risk_obj.factors.model_dump()
        score = float(fire_risk_obj.risk_score)
        level = fire_risk_obj.risk_level
    elif agent_type == "flood":
        r = compute_flood_risk(zone.id, zone.name, wx["rain_mm"], wx["humidity_pct"])
        factors = asdict(r.factors)
        score = r.flood_probability
        level = r.risk_level
    elif agent_type == "water":
        r = compute_water_risk(zone.id, zone.name, wx["temperature_c"])
        factors = asdict(r.factors)
        score = r.shortage_probability
        level = r.risk_level
    else:  # electricity
        real_outage = await get_zone_outage_status(zone.id)
        r = compute_electricity_risk(zone.id, zone.name, wx["temperature_c"], real_outage=real_outage)
        factors = asdict(r.factors)
        score = r.outage_probability
        level = r.risk_level

    result = generate_xai(agent_type, zone.id, zone.name, score, level, factors)
    return asdict(result)


@app.get("/api/agents/notifications/{zone_id}")
async def api_notifications(zone_id: str):
    """Notification Agent — stakeholder alerts for the zone."""
    zones_by_id = _zones_by_id()
    zone = zones_by_id.get(zone_id)
    if zone is None:
        raise HTTPException(status_code=404, detail=f"Unknown zone_id: {zone_id}")

    ndvi_values = scenario.read_ndvi()
    fire_risk_obj = await _compute_zone_risk(zone, ndvi_values)
    wx = await _get_zone_weather_simple(zone)

    flood = compute_flood_risk(zone.id, zone.name, wx["rain_mm"], wx["humidity_pct"])
    water = compute_water_risk(zone.id, zone.name, wx["temperature_c"])
    real_outage = await get_zone_outage_status(zone.id)
    elec = compute_electricity_risk(zone.id, zone.name, wx["temperature_c"], real_outage=real_outage)

    notifications = generate_notifications(
        zone_id=zone.id,
        zone_name=zone.name,
        fire_score=float(fire_risk_obj.risk_score),
        flood_score=flood.flood_probability,
        water_score=water.shortage_probability,
        electricity_score=elec.outage_probability,
        electricity_active_outage=elec.active_outage,
    )
    return [asdict(n) for n in notifications]


@app.get("/api/tourist/dashboard/{zone_id}")
async def api_tourist_dashboard(zone_id: str):
    """
    Complete multi-agent tourist dashboard for a zone.
    Runs all 6 agents in parallel and returns a unified response.
    """
    zones_by_id = _zones_by_id()
    zone = zones_by_id.get(zone_id)
    if zone is None:
        raise HTTPException(status_code=404, detail=f"Unknown zone_id: {zone_id}")

    ndvi_values = scenario.read_ndvi()
    fire_risk_obj, wx, real_outage = await asyncio.gather(
        _compute_zone_risk(zone, ndvi_values),
        _get_zone_weather_simple(zone),
        get_zone_outage_status(zone.id),
    )

    # Run all secondary agents in parallel
    flood, water, elec = await asyncio.gather(
        asyncio.to_thread(compute_flood_risk, zone.id, zone.name, wx["rain_mm"], wx["humidity_pct"]),
        asyncio.to_thread(compute_water_risk, zone.id, zone.name, wx["temperature_c"]),
        asyncio.to_thread(compute_electricity_risk, zone.id, zone.name, wx["temperature_c"], real_outage),
    )

    fire_score = float(fire_risk_obj.risk_score)
    flood_score = flood.flood_probability
    water_score = water.shortage_probability
    elec_score = elec.outage_probability

    tourism, emergency = await asyncio.gather(
        asyncio.to_thread(
            compute_tourism_recommendation,
            zone.id, zone.name, fire_score, flood_score, water_score, elec_score,
        ),
        asyncio.to_thread(
            compute_emergency_plan,
            zone.id, zone.name, fire_score, flood_score, water_score, elec_score,
        ),
    )

    notifications = generate_notifications(
        zone.id, zone.name, fire_score, flood_score, water_score, elec_score, elec.active_outage
    )

    # Build agent status cards
    def _card(name, key, icon, score, level, metric, simulated=True):
        labels = {"low": "All Clear", "medium": "Watch", "high": "Warning", "critical": "Critical"}
        return {
            "agent_name": name, "agent_key": key, "icon": icon,
            "risk_level": level, "risk_score": round(score, 1),
            "status_label": labels.get(level, "Unknown"),
            "key_metric": metric, "is_simulated": simulated,
        }

    fire_label = f"{fire_score:.0f}/100 fire probability"
    agent_cards = [
        _card("Fire Intelligence", "fire", "🔥", fire_score, fire_risk_obj.risk_level, fire_label, simulated=False),
        _card("Flood Intelligence", "flood", "🌊", flood_score, flood.risk_level, f"{flood_score:.0f}/100 flood probability"),
        _card("Water Resources", "water", "💧", water_score, water.risk_level, f"{flood.factors.rainfall_mm:.0f} mm rainfall · {water.factors.reservoir_level_pct:.0f}% reservoir"),
        _card("Electricity & Infrastructure", "electricity", "⚡", elec_score, elec.risk_level, f"{elec.hotel_availability_pct:.0f}% hotels with power"),
        _card("Tourism Intelligence", "tourism", "🗺️", 100 - tourism.overall_safety_score, "low" if tourism.overall_safety_score >= 75 else "medium", f"Safety: {tourism.overall_safety_score:.0f}/100"),
        _card("Emergency Optimization", "emergency", "🚨", emergency.priority_score, emergency.overall_priority, f"Priority: {emergency.overall_priority.upper()}"),
    ]

    overall_safety = (
        (100 - fire_score) * 0.30 +
        (100 - flood_score) * 0.25 +
        (100 - water_score) * 0.20 +
        (100 - elec_score) * 0.15 +
        tourism.overall_safety_score * 0.10
    )

    return {
        "zone_id": zone.id,
        "zone_name": zone.name,
        "overall_safety_score": round(overall_safety, 1),
        "agent_cards": agent_cards,
        "fire": {
            "risk_score": fire_score,
            "risk_level": fire_risk_obj.risk_level,
            "factors": fire_risk_obj.factors.model_dump(),
        },
        "flood": asdict(flood),
        "water": asdict(water),
        "electricity": asdict(elec),
        "tourism": asdict(tourism),
        "emergency": asdict(emergency),
        "notifications": [asdict(n) for n in notifications],
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/api/agents/status")
async def api_agents_status():
    """Returns current status of all agents across all zones — for the global tourist dashboard."""
    zones = _load_zones()
    ndvi_values = scenario.read_ndvi()

    # Compute fire risks in parallel
    fire_risks = await asyncio.gather(*(_compute_zone_risk(z, ndvi_values) for z in zones))

    zone_summaries = []
    for zone, fire_risk in zip(zones, fire_risks):
        zone_summaries.append({
            "zone_id": zone.id,
            "zone_name": zone.name,
            "lat": zone.lat,
            "lon": zone.lon,
            "fire_risk_score": fire_risk.risk_score,
            "fire_risk_level": fire_risk.risk_level,
            "overall_safe": fire_risk.risk_score < 50,
        })

    return {
        "zones": zone_summaries,
        "agent_count": 7,  # fire + flood + water + electricity + tourism + emergency + xai + notification
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


# ─── Scenario & NDVI API ──────────────────────────────────────────────────────

@app.post("/api/scenario/override")
async def api_scenario_override(body: ScenarioOverride):
    zones_by_id = _zones_by_id()
    if body.zone_id not in zones_by_id:
        raise HTTPException(status_code=404, detail=f"Unknown zone_id: {body.zone_id}")
    scenario.override_zone_factors(
        body.zone_id,
        temperature_c=body.temperature_c,
        wind_kmh=body.wind_kmh,
        humidity_pct=body.humidity_pct,
        rain_mm=body.rain_mm,
        active_fires_nearby=body.active_fires_nearby,
        ndvi=body.ndvi,
    )
    return {"ok": True, "overrides": scenario.get_factor_overrides(body.zone_id)}


@app.post("/api/scenario/reset")
async def api_scenario_reset():
    values = scenario.reset_all_ndvi()
    return {"ok": True, "ndvi": values}


@app.post("/api/ndvi/refresh")
async def api_ndvi_refresh(background_tasks: BackgroundTasks):
    zones = [{"id": z.id, "lat": z.lat, "lon": z.lon} for z in _load_zones()]
    background_tasks.add_task(_run_ndvi_refresh, zones)
    return {
        "ok": True,
        "message": "Real NDVI refresh started in the background. This can take "
        "several minutes (satellite data + AppEEARS task queue). Poll "
        "GET /api/ndvi/status for progress.",
    }


async def _run_ndvi_refresh(zones: list[dict]) -> None:
    cache = await refresh_real_ndvi(zones)
    if cache is None:
        logging.getLogger(__name__).warning(
            "Background NDVI refresh failed - check EARTHDATA_USERNAME/EARTHDATA_PASSWORD"
        )


@app.get("/api/ndvi/status")
async def api_ndvi_status():
    zones = _load_zones()
    cache = load_real_cache()
    return {
        "real_cache_available": cache is not None,
        "fetched_at": cache["fetched_at"] if cache else None,
        "zones": [
            {"zone_id": z.id, **scenario.ndvi_source_for_zone(z.id)} for z in zones
        ],
        "earthdata_credentials_configured": bool(
            os.getenv("EARTHDATA_USERNAME") and os.getenv("EARTHDATA_PASSWORD")
        ),
    }


# ─── Hotel Resilience Dashboard ────────────────────────────────────────────────

@app.post("/api/hotels/declare", response_model=HotelStatus)
async def api_hotel_declare(body: HotelDeclaration):
    """Hotels self-report their own operational status. Upserts by
    (zone_id, hotel_name) - re-declaring just updates the existing record."""
    zones_by_id = _zones_by_id()
    if body.zone_id not in zones_by_id:
        raise HTTPException(status_code=404, detail=f"Unknown zone_id: {body.zone_id}")

    record = db.upsert_hotel(body.zone_id, body.hotel_name, body.model_dump())
    return HotelStatus(**record)


@app.get("/api/hotels/{zone_id}", response_model=list[HotelStatus])
async def api_hotels_for_zone(zone_id: str):
    zones_by_id = _zones_by_id()
    if zone_id not in zones_by_id:
        raise HTTPException(status_code=404, detail=f"Unknown zone_id: {zone_id}")
    return [HotelStatus(**h) for h in db.list_hotels(zone_id)]


@app.delete("/api/hotels/{zone_id}/{hotel_name}")
async def api_hotel_delete(zone_id: str, hotel_name: str):
    deleted = db.delete_hotel(zone_id, hotel_name)
    if not deleted:
        raise HTTPException(status_code=404, detail="No such hotel declaration")
    return {"ok": True}


@app.get("/api/hotels/resilience/summary", response_model=HotelResilienceStats)
async def api_hotels_resilience():
    """Aggregate resilience stats across all declared hotels: % operational,
    generator/battery/solar coverage, resilience by zone, available rooms in
    zones currently at low/medium fire risk."""
    hotels = db.list_hotels()
    zones = [{"id": z.id, "name": z.name} for z in _load_zones()]
    fire_risks = await _compute_all_risks()
    zone_risk_by_id = {r.zone_id: r.risk_score for r in fire_risks}

    stats = compute_resilience_stats(hotels, zones, zone_risk_by_id)
    return HotelResilienceStats(**stats)


@app.get("/api/hotels/alternative/{zone_id}/{hotel_name}", response_model=HotelAlternativeResponse)
async def api_hotel_alternative(zone_id: str, hotel_name: str):
    """'Instead of recommending a hotel currently experiencing a power outage,
    the AI suggests nearby alternatives.' Checks the named hotel's declared
    status; if it lacks electricity or water, searches the same zone first,
    then neighboring zones, for an operational alternative."""
    zones_by_id = _zones_by_id()
    zone = zones_by_id.get(zone_id)
    if zone is None:
        raise HTTPException(status_code=404, detail=f"Unknown zone_id: {zone_id}")

    all_hotels = db.list_hotels()
    hotels_by_zone: dict[str, list[dict]] = {}
    for h in all_hotels:
        hotels_by_zone.setdefault(h["zone_id"], []).append(h)

    zone_names = {z.id: z.name for z in _load_zones()}
    result = find_hotel_alternative(
        zone_id, hotel_name, hotels_by_zone, zone.neighbors, zone_names
    )
    return HotelAlternativeResponse(**result)


# ─── Smart Tourist Route Planner ───────────────────────────────────────────────

@app.get("/api/route/airports")
async def api_route_airports():
    return [{"id": k, **v} for k, v in AIRPORTS.items()]


def _resolve_route_point(point_id: str, zones_by_id: dict[str, Zone]) -> tuple[float, float, str] | None:
    if point_id in zones_by_id:
        z = zones_by_id[point_id]
        return z.lat, z.lon, z.name
    if point_id in AIRPORTS:
        a = AIRPORTS[point_id]
        return a["lat"], a["lon"], a["name"]
    return None


@app.get("/api/route/plan", response_model=RoutePlanResponse)
async def api_route_plan(
    origin: str,
    destination: str,
    origin_lat: float | None = None,
    origin_lon: float | None = None,
):
    """
    Real road routing (OSRM) between two points, with hazard-aware alternative
    selection. `destination` is a zone_id (see /api/zones) or an airport id
    (see /api/route/airports). `origin` is normally the same, EXCEPT when
    `origin_lat`/`origin_lon` are both given (e.g. the browser's real
    Geolocation position) - then those coordinates are used directly and
    `origin` is treated as just a display label (e.g. "current_location").
    The "safest path" logic that picks between OSRM's real alternative
    routes is documented in backend/route_planner.py.
    """
    zones_by_id = _zones_by_id()

    if origin_lat is not None and origin_lon is not None:
        o = (origin_lat, origin_lon, "Your location")
    else:
        o = _resolve_route_point(origin, zones_by_id)
        if o is None:
            raise HTTPException(status_code=404, detail=f"Unknown origin: {origin}")

    d = _resolve_route_point(destination, zones_by_id)
    if d is None:
        raise HTTPException(status_code=404, detail=f"Unknown destination: {destination}")

    fire_risks = await _compute_all_risks()
    hazard_zones = [
        {"lat": r.lat, "lon": r.lon, "name": r.zone_name, "risk_level": r.risk_level}
        for r in fire_risks
        if r.risk_level in ("high", "critical")
    ]

    result = await plan_route(o[0], o[1], d[0], d[1], hazard_zones)
    if result is None:
        raise HTTPException(
            status_code=502,
            detail="Routing service (OSRM) unavailable right now - could not compute a real route.",
        )

    return RoutePlanResponse(
        origin={"id": origin, "name": o[2]},
        destination={"id": destination, "name": d[2]},
        **result,
    )


# ─── Automatic Hotel Notifications (real email delivery) ─────────────────────

def _build_notification_email_body(notif, zone: Zone) -> str:
    map_url = "http://localhost:8000/"  # live risk map for this deployment
    actions = "\n".join(f"  - {a}" for a in notif.actions)
    return (
        f"{notif.message}\n\n"
        f"Risk level: {notif.severity.upper()}\n"
        f"Zone: {zone.name}\n"
        f"As of: {notif.timestamp}\n"
        f"Source: {notif.agent_source}\n\n"
        f"Recommended actions:\n{actions}\n\n"
        f"Live risk map / current status: {map_url}\n\n"
        "---\n"
        "Tunisia Guardian AI - automated hazard monitoring.\n"
        "This is an automated message from the multi-agent monitoring platform."
    )


@app.post("/api/notifications/send/{zone_id}")
async def api_send_hotel_notifications(zone_id: str):
    """
    'When a hazard is predicted, hotels receive automatic email alerts.'
    Computes current hazard notifications for the zone, and emails every
    hotel that has declared a contact_email (via /api/hotels/declare) whose
    stakeholder-targeted notification applies to hotels. Real SMTP send if
    SMTP_HOST/SMTP_USERNAME/SMTP_PASSWORD are configured (see README); if
    not, each notification is logged instead of sent, and the response says
    so explicitly rather than claiming success.
    """
    zones_by_id = _zones_by_id()
    zone = zones_by_id.get(zone_id)
    if zone is None:
        raise HTTPException(status_code=404, detail=f"Unknown zone_id: {zone_id}")

    ndvi_values = scenario.read_ndvi()
    fire_risk_obj, wx, real_outage = await asyncio.gather(
        _compute_zone_risk(zone, ndvi_values),
        _get_zone_weather_simple(zone),
        get_zone_outage_status(zone.id),
    )
    flood = compute_flood_risk(zone.id, zone.name, wx["rain_mm"], wx["humidity_pct"])
    water = compute_water_risk(zone.id, zone.name, wx["temperature_c"])
    elec = compute_electricity_risk(zone.id, zone.name, wx["temperature_c"], real_outage)

    notifications = generate_notifications(
        zone.id, zone.name,
        float(fire_risk_obj.risk_score), flood.flood_probability,
        water.shortage_probability, elec.outage_probability, elec.active_outage,
    )
    hotel_notifs = [n for n in notifications if n.stakeholder == "hotel"]

    if not hotel_notifs:
        return {
            "ok": True,
            "smtp_configured": email_client.is_configured(),
            "message": "No active hazard notifications for hotels in this zone right now.",
            "sent": [],
        }

    hotels_with_email = [h for h in db.list_hotels(zone.id) if h.get("contact_email")]
    if not hotels_with_email:
        return {
            "ok": True,
            "smtp_configured": email_client.is_configured(),
            "message": f"{len(hotel_notifs)} active hazard notification(s), but no hotels in "
            "this zone have declared a contact email yet (see /hotel-portal).",
            "sent": [],
        }

    results = []
    for notif in hotel_notifs:
        subject = f"[Tunisia Guardian AI] {notif.severity.upper()} - {notif.title}"
        body = _build_notification_email_body(notif, zone)
        for hotel in hotels_with_email:
            send_result = email_client.send_notification_email(hotel["contact_email"], subject, body)
            results.append(
                {
                    "hotel_name": hotel["hotel_name"],
                    "to_email": hotel["contact_email"],
                    "notification_title": notif.title,
                    "severity": notif.severity,
                    **send_result,
                }
            )

    return {
        "ok": True,
        "smtp_configured": email_client.is_configured(),
        "notifications_generated": len(hotel_notifs),
        "hotels_notified": len(hotels_with_email),
        "sent": results,
    }


# ─── AI Tourist Guide Chat ─────────────────────────────────────────────────

@app.post("/api/chat", response_model=ChatResponse)
async def api_chat(body: ChatRequest):
    """
    Conversational tourist guide, grounded in this platform's own live data
    (per-zone fire risk, hotel resilience stats, static site descriptions)
    instead of freeform LLM invention. If the local Ollama service is
    unreachable, chat_reply() returns an explicit "guide unavailable"
    message rather than silently failing or claiming an AI answer that
    didn't happen - same honesty discipline as the rest of this project.
    """
    if not body.messages:
        raise HTTPException(status_code=400, detail="messages must not be empty")

    lang = body.lang if body.lang in ("fr", "en", "ar") else "fr"

    zones = _load_zones()
    fire_risks = await _compute_all_risks()
    zones_context = [
        {
            "id": z.id,
            "name": z.name,
            "type": z.type,
            "fire_risk_score": r.risk_score,
            "fire_risk_level": r.risk_level,
        }
        for z, r in zip(zones, fire_risks)
    ]

    zone_risk_by_id = {r.zone_id: r.risk_score for r in fire_risks}
    hotels = db.list_hotels()
    hotel_summary = compute_resilience_stats(
        hotels, [{"id": z.id, "name": z.name} for z in zones], zone_risk_by_id
    )

    reply, used_llm = await chat_reply(
        [m.model_dump() for m in body.messages], zones_context, hotel_summary, lang
    )
    return ChatResponse(reply=reply, used_llm=used_llm, lang=lang)
