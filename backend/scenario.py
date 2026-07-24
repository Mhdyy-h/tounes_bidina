import json
from pathlib import Path

from backend.ndvi_cache import load_real_cache

NDVI_PATH = Path(__file__).resolve().parent.parent / "data" / "ndvi_simulated.json"
DEFAULT_NDVI = 0.55

# In-memory demo overrides for weather/fire/ndvi factors, keyed by zone_id.
# Ephemeral by design (reset on server restart or on /api/scenario/reset) and
# always takes priority over both the real satellite cache and the simulated
# default, so the demo button reliably forces whatever it asks for.
_factor_overrides: dict[str, dict] = {}


def read_simulated_ndvi() -> dict[str, float]:
    with open(NDVI_PATH, encoding="utf-8") as f:
        return json.load(f)


def read_ndvi() -> dict[str, float]:
    """Effective NDVI baseline per zone (before demo overrides are applied):
    real MODIS composite where available, simulated default otherwise."""
    values = read_simulated_ndvi()
    real_cache = load_real_cache()
    if real_cache:
        for zone_id, entry in real_cache.get("zones", {}).items():
            if zone_id in values:
                values[zone_id] = entry["ndvi"]
    return values


def ndvi_source_for_zone(zone_id: str) -> dict:
    """Describes where a zone's NDVI baseline actually comes from - used to
    build an honest source_datasets label, independent of any demo override."""
    real_cache = load_real_cache()
    if real_cache and zone_id in real_cache.get("zones", {}):
        return {
            "is_real": True,
            "composite_date": real_cache["zones"][zone_id]["composite_date"],
            "fetched_at": real_cache["fetched_at"],
        }
    return {"is_real": False}


def reset_all_ndvi() -> dict[str, float]:
    _factor_overrides.clear()
    return read_ndvi()


def override_zone_factors(
    zone_id: str,
    temperature_c: float | None = None,
    wind_kmh: float | None = None,
    humidity_pct: float | None = None,
    rain_mm: float | None = None,
    active_fires_nearby: int | None = None,
    ndvi: float | None = None,
) -> None:
    """Force weather/fire/ndvi factors for a zone during a demo, bypassing live
    APIs and the real NDVI cache entirely for the fields provided (None fields
    keep using live/fallback/real data)."""
    overrides = {
        k: v
        for k, v in {
            "temperature_c": temperature_c,
            "wind_kmh": wind_kmh,
            "humidity_pct": humidity_pct,
            "rain_mm": rain_mm,
            "active_fires_nearby": active_fires_nearby,
            "ndvi": ndvi,
        }.items()
        if v is not None
    }
    if overrides:
        _factor_overrides[zone_id] = overrides
    else:
        _factor_overrides.pop(zone_id, None)


def get_factor_overrides(zone_id: str) -> dict:
    return _factor_overrides.get(zone_id, {})
