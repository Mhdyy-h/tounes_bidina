"""
Loads the trained wildfire model once and serves live predictions.

If the model files are missing (e.g. `python -m training.train_fire` was never
run), `is_available()` returns False and callers are expected to fall back to
the rule-based risk engine (backend/risk_engine.py) - this module never raises
to a caller, matching the fallback pattern used for every other external
dependency in this project (weather, FIRMS, Ollama).
"""

import json
from pathlib import Path

import joblib

MODELS_DIR = Path(__file__).resolve().parent.parent / "models"
MODEL_PATH = MODELS_DIR / "wildfire_model.pkl"
META_PATH = MODELS_DIR / "wildfire_model_meta.json"

_model = None
_meta = None


def _load():
    global _model, _meta
    if _model is not None:
        return
    if not MODEL_PATH.exists() or not META_PATH.exists():
        return
    _model = joblib.load(MODEL_PATH)
    with open(META_PATH, encoding="utf-8") as f:
        _meta = json.load(f)


def is_available() -> bool:
    _load()
    return _model is not None


def get_meta() -> dict | None:
    _load()
    return _meta


def _explain(features: dict) -> str:
    importances = _meta["feature_importances"]
    stats = _meta["feature_stats_by_class"]
    top_features = sorted(importances, key=importances.get, reverse=True)[:2]

    labels = {
        "temperature_c": ("température", "°C"),
        "humidity_pct": ("humidité", "%"),
        "wind_kmh": ("vent", "km/h"),
        "rain_mm": ("pluie", "mm"),
    }

    parts = []
    for feat in top_features:
        value = features[feat]
        fire_mean = stats[feat]["fire_mean"]
        not_fire_mean = stats[feat]["not_fire_mean"]
        name, unit = labels[feat]
        closer_to_fire = abs(value - fire_mean) < abs(value - not_fire_mean)
        lean = "proche des journées à risque" if closer_to_fire else "proche des journées sans risque"
        parts.append(
            f"{name} à {value:.1f}{unit} ({lean} historiquement : "
            f"moyenne incendie {fire_mean:.1f}{unit} vs sans incendie {not_fire_mean:.1f}{unit})"
        )

    return "Facteurs les plus déterminants pour ce modèle : " + "; ".join(parts) + "."


def predict_fire_risk(
    temperature_c: float, humidity_pct: float, wind_kmh: float, rain_mm: float
) -> dict | None:
    """Returns None if the model isn't trained/available - caller must fall back."""
    _load()
    if _model is None:
        return None

    features = {
        "temperature_c": temperature_c,
        "humidity_pct": humidity_pct,
        "wind_kmh": wind_kmh,
        "rain_mm": rain_mm,
    }
    X = [[features[f] for f in _meta["features"]]]
    fire_probability = float(_model.predict_proba(X)[0][1])
    prediction = "fire" if fire_probability >= 0.5 else "not_fire"
    confidence = max(fire_probability, 1 - fire_probability)

    return {
        "prediction": prediction,
        "fire_probability": round(fire_probability, 4),
        "confidence": round(confidence, 4),
        "explanation": _explain(features),
        "model_version": _meta["trained_at"],
        "dataset_source": _meta["dataset_source"],
    }
