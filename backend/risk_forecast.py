"""
Multi-day risk forecast: reuses the exact same composite scoring
(backend/ml_risk.compute_composite_risk) with real forecasted weather
(Open-Meteo daily forecast, backend/weather_client.get_forecast) in place of
current conditions.

Honesty note: NDVI and active-fire count are held at today's most recently
known values for the whole forecast window. Neither is forecastable - NDVI is
a satellite composite product with a multi-week cadence, and fire ignition is
not predictable from weather alone. This is a real limitation of the forecast
(only the weather-driven component of the score is truly forward-looking) and
is stated explicitly in the API response rather than left implicit.
"""

from backend.ml_risk import compute_composite_risk
from backend.models import RiskFactors
from backend.weather_client import get_forecast


async def compute_forecast(
    lat: float, lon: float, ndvi: float, active_fires_nearby: int, days: int = 3
) -> list[dict] | None:
    """Returns None only if the real Open-Meteo forecast call itself failed -
    callers must handle that by saying so, never by fabricating a forecast."""
    forecast_days = await get_forecast(lat, lon, days=days)
    if forecast_days is None:
        return None

    results = []
    for day in forecast_days:
        factors = RiskFactors(
            temperature_c=day["temperature_c"],
            wind_kmh=day["wind_kmh"],
            humidity_pct=day["humidity_pct"],
            rain_mm=day["rain_mm"],
            active_fires_nearby=active_fires_nearby,
            ndvi=ndvi,
        )
        score, level, ml_result = compute_composite_risk(factors)
        results.append(
            {
                "date": day["date"],
                "risk_score": score,
                "risk_level": level,
                "temperature_c": day["temperature_c"],
                "humidity_pct": day["humidity_pct"],
                "wind_kmh": day["wind_kmh"],
                "rain_mm": day["rain_mm"],
                "fire_probability": ml_result["fire_probability"] if ml_result else None,
            }
        )
    return results
