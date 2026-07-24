"""
Refreshes data/ndvi_real_cache.json with real MODIS NDVI (MOD13Q1.061) for all
zones, via NASA Earthdata / AppEEARS (backend/earthdata_client.py).

This is a periodic job, not a live request handler: AppEEARS point tasks take
minutes to process, and MOD13Q1 is a 16-day composite anyway, so refreshing
once a day (or even once a week) is already more often than the underlying data
changes. Run it manually before a demo, or on a schedule (cron/Task Scheduler).
The running app can also trigger this in the background via POST /api/ndvi/refresh.

Requires a free NASA Earthdata Login account: https://urs.earthdata.nasa.gov/
Set EARTHDATA_USERNAME and EARTHDATA_PASSWORD as environment variables.

Run: python -m training.fetch_real_ndvi
"""

import asyncio
import json
from pathlib import Path

from backend.ndvi_cache import refresh_real_ndvi

ZONES_PATH = Path(__file__).resolve().parent.parent / "data" / "zones.json"


async def main():
    with open(ZONES_PATH, encoding="utf-8") as f:
        zones = json.load(f)

    print(f"Requesting real MODIS NDVI for {len(zones)} zones via NASA Earthdata/AppEEARS...")
    print("This submits an async satellite data task and can take several minutes.")

    def on_submitted(task_id: str):
        print(f"Task submitted: {task_id}")
        print(
            f"If this script times out before it finishes, DON'T resubmit - just run:\n"
            f"  python -m training.check_ndvi_task {task_id}"
        )

    cache = await refresh_real_ndvi(
        [{"id": z["id"], "lat": z["lat"], "lon": z["lon"]} for z in zones],
        on_task_submitted=on_submitted,
    )

    if cache is None:
        print(
            "FAILED: could not fetch real NDVI (check EARTHDATA_USERNAME/"
            "EARTHDATA_PASSWORD, network, or NASA Earthdata service status). "
            "data/ndvi_real_cache.json was not modified - the app will keep "
            "using data/ndvi_simulated.json."
        )
        return

    results = cache["zones"]
    print(f"Saved real NDVI for {len(results)}/{len(zones)} zones -> {Path('data/ndvi_real_cache.json')}")
    for zone_id, values in results.items():
        print(f"  {zone_id}: NDVI={values['ndvi']} (composite date {values['composite_date']})")

    missing = {z["id"] for z in zones} - set(results)
    if missing:
        print(f"  No valid composite found for: {', '.join(missing)} (will use simulated fallback)")


if __name__ == "__main__":
    asyncio.run(main())
