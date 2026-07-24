"""
Debug helper: re-downloads the raw AppEEARS results CSV for an already-done
task (no resubmission) and saves it untouched, so we can inspect real column
names and raw values instead of guessing at the parsing bug.

Run: python -m training.debug_ndvi_csv <task_id>
"""

import asyncio
import sys
from pathlib import Path

import httpx

from backend.earthdata_client import APPEEARS_BASE, login

OUT_PATH = Path(__file__).resolve().parent.parent / "data" / "ndvi_debug_raw.csv"


async def main(task_id: str):
    token = await login()
    if token is None:
        print("FAILED: could not authenticate to NASA Earthdata")
        return

    async with httpx.AsyncClient(timeout=30.0) as client:
        bundle_resp = await client.get(
            f"{APPEEARS_BASE}/bundle/{task_id}", headers={"Authorization": f"Bearer {token}"}
        )
        bundle_resp.raise_for_status()
        files = bundle_resp.json()["files"]
        print("Files in bundle:")
        for f in files:
            print(f"  {f['file_name']}")

        csv_file = next((f for f in files if f["file_name"].endswith("-results.csv")), None)
        if csv_file is None:
            print("No -results.csv file found in bundle.")
            return

        file_resp = await client.get(
            f"{APPEEARS_BASE}/bundle/{task_id}/{csv_file['file_id']}",
            headers={"Authorization": f"Bearer {token}"},
            follow_redirects=True,
        )
        file_resp.raise_for_status()

    OUT_PATH.write_text(file_resp.text, encoding="utf-8")
    print(f"Saved raw CSV -> {OUT_PATH}")
    lines = file_resp.text.splitlines()
    print(f"Total lines: {len(lines)}")
    print("Header:", lines[0] if lines else "(empty)")
    print("First 3 data rows:")
    for line in lines[1:4]:
        print(" ", line)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python -m training.debug_ndvi_csv <task_id>")
        sys.exit(1)
    asyncio.run(main(sys.argv[1]))
