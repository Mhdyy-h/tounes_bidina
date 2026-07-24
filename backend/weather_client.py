import logging

import httpx

from backend.cache import TTLCache

logger = logging.getLogger(__name__)

# Open-Meteo: free, real-time, no API key or signup required at all - this is
# what actually fixes "why is it 28C in mid-July" for every user of this app,
# with zero setup friction. https://open-meteo.com (non-commercial, <10k req/day).
OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"

FALLBACK = {"temperature_c": 28.0, "wind_kmh": 10.0, "humidity_pct": 45.0, "rain_mm": 0.0}

# Weather doesn't meaningfully change second to second - caching briefly means
# the frontend's live polling/streaming doesn't hammer Open-Meteo with near-
# identical requests for the same 6 coordinates every few seconds.
_cache = TTLCache(ttl_seconds=60)


async def get_weather(lat: float, lon: float) -> dict:
    """Returns real-time weather fields plus `is_live` (True only for a real
    successful Open-Meteo response) so callers can honestly label the source.
    No API key needed - only falls back to fixed defaults if the network/API
    call itself fails. Successful responses are cached for 60s; failures are
    never cached, so a transient outage is retried on the very next call."""
    cache_key = (round(lat, 4), round(lon, 4))
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        async with httpx.AsyncClient(timeout=6.0) as client:
            resp = await client.get(
                OPEN_METEO_URL,
                params={
                    "latitude": lat,
                    "longitude": lon,
                    "current": "temperature_2m,relative_humidity_2m,wind_speed_10m,precipitation",
                    "wind_speed_unit": "kmh",
                    "timezone": "auto",
                },
            )
            resp.raise_for_status()
            data = resp.json()["current"]

        result = {
            "temperature_c": float(data["temperature_2m"]),
            "wind_kmh": float(data["wind_speed_10m"]),
            "humidity_pct": float(data["relative_humidity_2m"]),
            "rain_mm": float(data["precipitation"]),
            "is_live": True,
        }
        _cache.set(cache_key, result)
        return result
    except Exception as exc:
        logger.warning("Open-Meteo call failed (%s), using fallback weather values", exc)
        return {**FALLBACK, "is_live": False}


_forecast_cache = TTLCache(ttl_seconds=3600)  # forecasts update a few times/day, not every minute


async def get_forecast(lat: float, lon: float, days: int = 3) -> list[dict] | None:
    """Returns real daily forecast data for the next `days` days (tomorrow
    onward, today excluded), or None if the call fails - callers must handle
    that (no fabricated forecast values). Each entry:
    {date, temperature_c, humidity_pct, wind_kmh, rain_mm}."""
    cache_key = (round(lat, 4), round(lon, 4), days)
    cached = _forecast_cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        async with httpx.AsyncClient(timeout=6.0) as client:
            resp = await client.get(
                OPEN_METEO_URL,
                params={
                    "latitude": lat,
                    "longitude": lon,
                    "daily": "temperature_2m_max,relative_humidity_2m_mean,wind_speed_10m_max,precipitation_sum",
                    "wind_speed_unit": "kmh",
                    "timezone": "auto",
                    "forecast_days": days + 1,  # index 0 is today, we want tomorrow onward
                },
            )
            resp.raise_for_status()
            data = resp.json()["daily"]

        result = [
            {
                "date": data["time"][i],
                "temperature_c": float(data["temperature_2m_max"][i]),
                "humidity_pct": float(data["relative_humidity_2m_mean"][i]),
                "wind_kmh": float(data["wind_speed_10m_max"][i]),
                "rain_mm": float(data["precipitation_sum"][i]),
            }
            for i in range(1, days + 1)
        ]
        _forecast_cache.set(cache_key, result)
        return result
    except Exception as exc:
        logger.warning("Open-Meteo forecast call failed (%s)", exc)
        return None
