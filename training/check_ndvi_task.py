"""
Resume checking a previously-submitted AppEEARS NDVI task instead of
resubmitting one. training/fetch_real_ndvi.py stops polling after 30 minutes,
but AppEEARS keeps processing the task server-side regardless - resubmitting
would just queue a duplicate job and make you wait even longer.

Run: python -m training.check_ndvi_task <task_id>
(the task_id is printed by fetch_real_ndvi.py right after submission)
"""

import asyncio
import sys

from backend.earthdata_client import download_results, get_task_status, login
from backend.ndvi_cache import build_and_save_cache


async def main(task_id: str):
    token = await login()
    if token is None:
        print("FAILED: could not authenticate to NASA Earthdata (check EARTHDATA_USERNAME/EARTHDATA_PASSWORD)")
        return

    status = await get_task_status(token, task_id)
    print(f"Task {task_id} status: {status}")

    if status == "done":
        results = await download_results(token, task_id)
        if results is None:
            print("FAILED: task is done but downloading/parsing its results failed.")
            return
        build_and_save_cache(results)
        print(f"Saved real NDVI for {len(results)} zones -> data/ndvi_real_cache.json")
        for zone_id, values in results.items():
            print(f"  {zone_id}: NDVI={values['ndvi']} (composite date {values['composite_date']})")
    elif status == "error":
        print("FAILED: AppEEARS reported an error processing this task - you'll need to resubmit (python -m training.fetch_real_ndvi).")
    else:
        print(f"Still processing (status={status}). Try again in a few minutes:")
        print(f"  python -m training.check_ndvi_task {task_id}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python -m training.check_ndvi_task <task_id>")
        sys.exit(1)
    asyncio.run(main(sys.argv[1]))
