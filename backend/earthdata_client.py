"""
Real MODIS NDVI via NASA Earthdata / AppEEARS (https://appeears.earthdatacloud.nasa.gov).

Honesty note on "real-time": MOD13Q1.061 is a 16-day composite product - MODIS
revisits, clouds get filtered out, and the composite itself takes time to process.
There is no such thing as literally real-time NDVI from any satellite anywhere;
the best physically-possible answer is "the most recent completed composite",
which is what this module fetches and labels with its actual composite date.

AppEEARS point-extraction tasks are asynchronous and typically take 1-10+ minutes
to process - this is NOT meant to be called inside a live HTTP request. Use
training/fetch_real_ndvi.py to refresh data/ndvi_real_cache.json periodically
(e.g. once a day, since a 16-day product never changes faster than that), and the
backend reads from that cache. Requires a free NASA Earthdata Login account
(https://urs.earthdata.nasa.gov/) - set EARTHDATA_USERNAME / EARTHDATA_PASSWORD.
"""

import asyncio
import csv as csv_module
import io
import logging
import os
from datetime import datetime, timedelta, timezone

import httpx

logger = logging.getLogger(__name__)

APPEEARS_BASE = "https://appeears.earthdatacloud.nasa.gov/api"
PRODUCT = "MOD13Q1.061"
LAYER = "_250m_16_days_NDVI"


async def login() -> str | None:
    username = os.getenv("EARTHDATA_USERNAME")
    password = os.getenv("EARTHDATA_PASSWORD")
    if not username or not password:
        logger.warning(
            "EARTHDATA_USERNAME/EARTHDATA_PASSWORD not set - cannot fetch real NDVI"
        )
        return None

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(f"{APPEEARS_BASE}/login", auth=(username, password))
            resp.raise_for_status()
            return resp.json()["token"]
    except Exception as exc:
        logger.warning("AppEEARS login failed (%s)", exc)
        return None


async def submit_task(token: str, zones: list[dict], task_name: str) -> str | None:
    """zones: list of {"id": str, "lat": float, "lon": float}"""
    end_date = datetime.now(timezone.utc).date()
    start_date = end_date - timedelta(days=60)  # spans several 16-day composites

    body = {
        "task_type": "point",
        "task_name": task_name,
        "params": {
            "dates": [
                {
                    "startDate": start_date.strftime("%m-%d-%Y"),
                    "endDate": end_date.strftime("%m-%d-%Y"),
                }
            ],
            "layers": [{"product": PRODUCT, "layer": LAYER}],
            "coordinates": [
                {"id": z["id"], "latitude": z["lat"], "longitude": z["lon"]} for z in zones
            ],
        },
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{APPEEARS_BASE}/task", json=body, headers={"Authorization": f"Bearer {token}"}
            )
            resp.raise_for_status()
            return resp.json()["task_id"]
    except Exception as exc:
        logger.warning("AppEEARS task submission failed (%s)", exc)
        return None


async def get_task_status(token: str, task_id: str) -> str:
    """Single-shot status check: 'pending', 'processing', 'done', 'error', or
    'unknown' (on a transient request failure - not a task failure, safe to retry)."""
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                f"{APPEEARS_BASE}/task/{task_id}", headers={"Authorization": f"Bearer {token}"}
            )
            resp.raise_for_status()
            return resp.json().get("status", "unknown")
    except Exception as exc:
        logger.warning("AppEEARS task status check failed (%s)", exc)
        return "unknown"


async def poll_task(token: str, task_id: str, timeout_s: int = 1800, interval_s: int = 15) -> str:
    """Polls until 'done'/'error' or timeout_s elapses. Returns 'done', 'error',
    or 'timeout'. NOTE: a 'timeout' here only means this function stopped
    waiting - AppEEARS keeps processing the task server-side regardless, so
    training/check_ndvi_task.py can resume checking the same task_id later
    without resubmitting."""
    elapsed = 0
    while elapsed < timeout_s:
        status = await get_task_status(token, task_id)
        logger.info("AppEEARS task %s status: %s", task_id, status)
        if status in ("done", "error"):
            return status
        await asyncio.sleep(interval_s)
        elapsed += interval_s
    return "timeout"


def _parse_ndvi_csv(csv_text: str) -> dict[str, dict]:
    reader = csv_module.DictReader(io.StringIO(csv_text))
    ndvi_col = None
    latest_by_zone: dict[str, dict] = {}

    for row in reader:
        if ndvi_col is None:
            ndvi_col = next(
                (k for k in row if "NDVI" in k.upper() and "QC" not in k.upper() and "QA" not in k.upper()),
                None,
            )
            if ndvi_col is None:
                continue

        zone_id = row.get("ID")
        raw_value = row.get(ndvi_col)
        date_str = row.get("Date")
        if not zone_id or not date_str or raw_value in (None, "", "F"):
            continue

        try:
            # AppEEARS point-results CSVs already apply the product's scale
            # factor (confirmed by inspecting a real downloaded CSV: values
            # come through as e.g. 0.57, not the raw 5700 digital number) -
            # do NOT rescale again here. Fill/no-data pixels come through as
            # the raw sentinel -3000.0, which the range check below rejects.
            ndvi = float(raw_value)
        except ValueError:
            continue

        if not (-0.2 <= ndvi <= 1.0):
            continue  # fill/invalid value outside the physically valid NDVI range

        existing = latest_by_zone.get(zone_id)
        if existing is None or date_str > existing["composite_date"]:
            latest_by_zone[zone_id] = {"ndvi": round(ndvi, 3), "composite_date": date_str}

    return latest_by_zone


async def download_results(token: str, task_id: str) -> dict[str, dict] | None:
    """Returns {zone_id: {"ndvi": float, "composite_date": "YYYY-MM-DD"}}."""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            bundle_resp = await client.get(
                f"{APPEEARS_BASE}/bundle/{task_id}", headers={"Authorization": f"Bearer {token}"}
            )
            bundle_resp.raise_for_status()
            files = bundle_resp.json()["files"]

            csv_file = next((f for f in files if f["file_name"].endswith("-results.csv")), None)
            if csv_file is None:
                logger.warning("No results CSV in AppEEARS bundle for task %s", task_id)
                return None

            file_resp = await client.get(
                f"{APPEEARS_BASE}/bundle/{task_id}/{csv_file['file_id']}",
                headers={"Authorization": f"Bearer {token}"},
                follow_redirects=True,
            )
            file_resp.raise_for_status()
            return _parse_ndvi_csv(file_resp.text)
    except Exception as exc:
        logger.warning("AppEEARS bundle download failed (%s)", exc)
        return None


async def fetch_real_ndvi(
    zones: list[dict], task_name: str = "tunisia_guardian_ndvi", on_task_submitted=None
) -> dict[str, dict] | None:
    """End-to-end: login -> submit -> poll -> download. Returns None on any
    failure (never raises) so callers can keep serving the simulated cache.
    `on_task_submitted(task_id)`, if given, is called right after submission -
    use it to print/log the task_id immediately, since a poll timeout doesn't
    mean the task failed (see training/check_ndvi_task.py to resume by ID)."""
    token = await login()
    if token is None:
        return None

    task_id = await submit_task(token, zones, task_name)
    if task_id is None:
        return None

    logger.info("AppEEARS task submitted: %s", task_id)
    if on_task_submitted:
        on_task_submitted(task_id)

    status = await poll_task(token, task_id)
    if status != "done":
        logger.warning(
            "AppEEARS task %s did not complete within the polling window (status=%s). "
            "It is likely still processing on NASA's servers - check it later with "
            "`python -m training.check_ndvi_task %s` instead of resubmitting.",
            task_id, status, task_id,
        )
        return None

    return await download_results(token, task_id)
