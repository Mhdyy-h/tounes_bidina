"""
Combines the trained ML wildfire probability with the live/simulated signals
that the model itself doesn't see (satellite fire hotspots, vegetation index)
into the single 0-100 score shown on the map and in the tourist screen.

Composite weights (documented, not hidden in a black box):
  - ML fire probability (temperature/humidity/wind/rain, trained model): 0-50 pts
  - active_fires_nearby (NASA FIRMS, real satellite hotspots): 15 pts/fire, capped at 30
  - NDVI (SIMULATED vegetation dryness, data/ndvi_simulated.json): 0-20 pts

Falls back to the pure rule-based engine (backend/risk_engine.py) if the model
isn't trained/available - never raises to the caller.
"""

from inference.predict import get_meta, is_available, predict_fire_risk
from backend.models import RiskFactors
from backend.risk_engine import clamp, lerp_score, compute_risk_score, risk_level_from_score


def compute_composite_risk(factors: RiskFactors) -> tuple[int, str, dict | None]:
    """Returns (risk_score, risk_level, ml_prediction_dict_or_None)."""
    if not is_available():
        score, level = compute_risk_score(factors)
        return score, level, None

    ml_result = predict_fire_risk(
        factors.temperature_c, factors.humidity_pct, factors.wind_kmh, factors.rain_mm
    )
    if ml_result is None:
        score, level = compute_risk_score(factors)
        return score, level, None

    ml_component = ml_result["fire_probability"] * 50
    fires_component = min(factors.active_fires_nearby * 15, 30)
    ndvi_component = lerp_score(factors.ndvi, 0.6, 0.2, 20)

    total = ml_component + fires_component + ndvi_component
    score = int(round(clamp(total, 0, 100)))
    level = risk_level_from_score(score)

    return score, level, ml_result


def source_datasets_descriptor(source_info: dict) -> dict:
    meta = get_meta()
    ml_desc = (
        f"XGBoost classifier trained on {meta['dataset_source']} "
        f"(test accuracy {meta['test_metrics']['accuracy']}, ROC-AUC {meta['test_metrics']['roc_auc']}). "
        "See models/wildfire_model_meta.json for full training metadata."
        if meta
        else "ML model not trained/available - using rule-based fallback formula (backend/risk_engine.py)."
    )

    if source_info["weather_overridden"]:
        weather_desc = "Demo override - manually forced for this session (backend/scenario.py)"
    elif source_info["weather_is_live"]:
        weather_desc = "Open-Meteo live API (real-time, no key required)"
    else:
        weather_desc = "Fallback default (network/API call failed)"

    if source_info["fires_overridden"]:
        fires_desc = "Demo override - manually forced for this session (backend/scenario.py)"
    elif source_info["fires_is_live"]:
        fires_desc = "NASA FIRMS active fire hotspots (live satellite data)"
    else:
        fires_desc = "Fallback default (no FIRMS_API_KEY set, or call failed)"

    ndvi_source = source_info["ndvi_source"]
    if source_info["ndvi_overridden"]:
        ndvi_desc = "Demo override - manually forced for this session (backend/scenario.py)"
    elif ndvi_source.get("is_real"):
        ndvi_desc = (
            f"REAL MODIS NDVI (MOD13Q1.061, 250m 16-day composite) via NASA Earthdata/AppEEARS - "
            f"composite date {ndvi_source['composite_date']}, cache fetched {ndvi_source['fetched_at']}. "
            "Note: satellite NDVI is inherently a multi-week composite product, not instantaneous."
        )
    else:
        ndvi_desc = (
            "SIMULATED vegetation index - data/ndvi_simulated.json. Real NDVI not available "
            "(EARTHDATA_USERNAME/EARTHDATA_PASSWORD not set, or python -m training.fetch_real_ndvi "
            "hasn't been run yet)."
        )

    return {
        "weather": weather_desc,
        "fires": fires_desc,
        "ndvi": ndvi_desc,
        "ml_model": ml_desc,
    }
