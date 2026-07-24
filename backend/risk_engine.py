from backend.models import RiskFactors


def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def lerp_score(value: float, lo: float, hi: float, max_points: float) -> float:
    """Linear interpolation of `value` from range [lo, hi] to [0, max_points].
    Works for both increasing (lo < hi) and decreasing (lo > hi) ranges."""
    clamped = clamp(value, min(lo, hi), max(lo, hi))
    span = hi - lo
    if span == 0:
        return 0.0
    fraction = (clamped - lo) / span
    return clamp(fraction, 0.0, 1.0) * max_points


def risk_level_from_score(score: int) -> str:
    if score <= 24:
        return "low"
    elif score <= 49:
        return "medium"
    elif score <= 74:
        return "high"
    else:
        return "critical"


def compute_risk_score(factors: RiskFactors) -> tuple[int, str]:
    """
    Rule-based fallback scorer, used only when the trained ML model
    (backend/ml_risk.py, inference/predict.py) is unavailable.
    Weighted score 0-100:
      - temperature: linear 30-42C -> 0-20 pts
      - wind: linear 10-40km/h -> 0-20 pts
      - humidity: linear 50-10% -> 0-20 pts (lower humidity = higher risk)
      - active_fires_nearby: 15 pts per fire, capped at 30
      - ndvi: linear 0.6-0.2 -> 0-30 pts (lower ndvi = drier vegetation = higher risk)
    """
    temp_score = lerp_score(factors.temperature_c, 30, 42, 20)
    wind_score = lerp_score(factors.wind_kmh, 10, 40, 20)
    humidity_score = lerp_score(factors.humidity_pct, 50, 10, 20)
    fires_score = min(factors.active_fires_nearby * 15, 30)
    ndvi_score = lerp_score(factors.ndvi, 0.6, 0.2, 30)

    total = temp_score + wind_score + humidity_score + fires_score + ndvi_score
    score = int(round(clamp(total, 0, 100)))

    return score, risk_level_from_score(score)
