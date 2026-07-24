import logging
import math
import os

import httpx

from backend.cache import TTLCache

logger = logging.getLogger(__name__)

FIRMS_URL_TEMPLATE = (
    "https://firms.modaps.eosdis.nasa.gov/api/area/csv/{map_key}/VIIRS_SNPP_NRT/"
    "{west},{south},{east},{north}/1"
)

# VIIRS hotspot detections don't turn over anywhere near as fast as our
# polling cadence - a few minutes of staleness is a non-issue and saves
# hammering FIRMS with near-identical requests for the same 6 coordinates.
_cache = TTLCache(ttl_seconds=300)


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _bounding_box(lat: float, lon: float, radius_km: float) -> tuple[float, float, float, float]:
    # Rough degree-per-km approximation, padded, good enough to over-fetch then filter precisely.
    deg_lat = radius_km / 111.0
    deg_lon = radius_km / (111.0 * max(math.cos(math.radians(lat)), 0.1))
    return lon - deg_lon, lat - deg_lat, lon + deg_lon, lat + deg_lat


async def get_active_fires(lat: float, lon: float, radius_km: float = 15) -> tuple[int, bool]:
    """Returns (count, is_live) - is_live is True only for a real successful
    FIRMS API response, so callers can honestly label the data source."""
    map_key = os.getenv("FIRMS_API_KEY")
    if not map_key:
        logger.warning("FIRMS_API_KEY not set, using fallback active_fires_nearby=0")
        return 0, False

    cache_key = (round(lat, 4), round(lon, 4), radius_km)
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached

    west, south, east, north = _bounding_box(lat, lon, radius_km)
    url = FIRMS_URL_TEMPLATE.format(
        map_key=map_key, west=west, south=south, east=east, north=north
    )

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            lines = resp.text.strip().splitlines()

        if len(lines) <= 1:
            result = (0, True)
            _cache.set(cache_key, result)
            return result

        header = lines[0].split(",")
        lat_idx = header.index("latitude")
        lon_idx = header.index("longitude")

        count = 0
        for line in lines[1:]:
            fields = line.split(",")
            f_lat = float(fields[lat_idx])
            f_lon = float(fields[lon_idx])
            if _haversine_km(lat, lon, f_lat, f_lon) <= radius_km:
                count += 1
        result = (count, True)
        _cache.set(cache_key, result)
        return result
    except Exception as exc:
        logger.warning("FIRMS call failed (%s), using fallback active_fires_nearby=0", exc)
        return 0, False
