"""
Shared read/write/refresh logic for the real-NDVI cache
(data/ndvi_real_cache.json), used by the CLI refresh script
(training/fetch_real_ndvi.py), the task-resume script
(training/check_ndvi_task.py), and the live `/api/ndvi/refresh` endpoint so
none of them drift apart.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

from backend.earthdata_client import fetch_real_ndvi

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
REAL_CACHE_PATH = DATA_DIR / "ndvi_real_cache.json"

CACHE_SOURCE_LABEL = "NASA Earthdata / AppEEARS, MOD13Q1.061 250m 16-day NDVI composite"


def load_real_cache() -> dict | None:
    if not REAL_CACHE_PATH.exists():
        return None
    try:
        with open(REAL_CACHE_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def save_real_cache(cache: dict) -> None:
    REAL_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(REAL_CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2)


def build_and_save_cache(results: dict[str, dict]) -> dict:
    """results: {zone_id: {"ndvi": float, "composite_date": str}}."""
    cache = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "source": CACHE_SOURCE_LABEL,
        "zones": results,
    }
    save_real_cache(cache)
    return cache


async def refresh_real_ndvi(zones: list[dict], on_task_submitted=None) -> dict | None:
    """zones: list of {"id", "lat", "lon"}. Returns the saved cache dict, or
    None if the fetch failed (never raises - callers keep using whatever
    cache/simulated data they already had)."""
    results = await fetch_real_ndvi(zones, on_task_submitted=on_task_submitted)
    if results is None:
        return None
    return build_and_save_cache(results)
