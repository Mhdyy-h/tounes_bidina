"""
Cleans the raw Algerian Forest Fires Dataset (Bejaia + Sidi Bel-abbes regions,
June-Sept 2012) into a flat, typed table ready for model training.

Source: Abid, Faroudja. "Algerian Forest Fires Dataset." Zenodo, 2022.
DOI: 10.5281/zenodo.6515969 (mirrors the original UCI ML Repository dataset,
CC-BY-4.0). 244 instances, 2 regions x 122 daily records each.

The raw file is not a clean CSV: it embeds two region blocks back-to-back,
each with its own repeated header row and a free-text title line, and it has
known data-entry artifacts (stray whitespace inside numeric fields, e.g.
"14.6 9" instead of "14.69", and trailing spaces on column names/labels).
This module parses that structure explicitly rather than dropping bad rows.
"""

import logging
import re
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

RAW_PATH = Path(__file__).resolve().parent.parent / "data" / "raw" / "Algerian_forest_fires_dataset_UPDATE.csv"
CLEAN_PATH = Path(__file__).resolve().parent.parent / "data" / "processed" / "algerian_forest_fires_clean.csv"

COLUMN_MAP = {
    "day": "day",
    "month": "month",
    "year": "year",
    "temperature": "temperature_c",
    "rh": "humidity_pct",
    "ws": "wind_kmh",
    "rain": "rain_mm",
    "ffmc": "ffmc",
    "dmc": "dmc",
    "dc": "dc",
    "isi": "isi",
    "bui": "bui",
    "fwi": "fwi",
    "classes": "label_raw",
}

REGION_TITLES = {
    "bejaia region dataset": "Bejaia",
    "sidi-bel abbes region dataset": "Sidi-Bel Abbes",
}


def _clean_numeric(token: str) -> float:
    # Fixes known artifacts like "14.6 9" (stray space inside a float literal).
    token = re.sub(r"\s+", "", token)
    return float(token)


def load_clean_dataframe() -> pd.DataFrame:
    with open(RAW_PATH, encoding="utf-8") as f:
        lines = [line.strip() for line in f.readlines()]

    rows: list[dict] = []
    current_region: str | None = None
    header: list[str] | None = None

    for line in lines:
        if not line:
            continue

        lowered = line.lower()
        if lowered in REGION_TITLES:
            current_region = REGION_TITLES[lowered]
            header = None
            continue

        if lowered.startswith("day,month,year"):
            header = [COLUMN_MAP[h.strip().lower()] for h in line.split(",")]
            continue

        if header is None or current_region is None:
            continue

        fields = [f.strip() for f in line.split(",")]
        if len(fields) != len(header):
            logger.warning(
                "Skipping corrupted source row (expected %d fields, got %d): %r",
                len(header), len(fields), line,
            )
            continue

        record = dict(zip(header, fields))
        try:
            row = {
                "day": int(record["day"]),
                "month": int(record["month"]),
                "year": int(record["year"]),
                "temperature_c": _clean_numeric(record["temperature_c"]),
                "humidity_pct": _clean_numeric(record["humidity_pct"]),
                "wind_kmh": _clean_numeric(record["wind_kmh"]),
                "rain_mm": _clean_numeric(record["rain_mm"]),
                "ffmc": _clean_numeric(record["ffmc"]),
                "dmc": _clean_numeric(record["dmc"]),
                "dc": _clean_numeric(record["dc"]),
                "isi": _clean_numeric(record["isi"]),
                "bui": _clean_numeric(record["bui"]),
                "fwi": _clean_numeric(record["fwi"]),
                "region": current_region,
                "fire": 1 if record["label_raw"].strip().lower() == "fire" else 0,
            }
        except (ValueError, KeyError) as exc:
            logger.warning("Skipping row with unparseable value (%s): %r", exc, line)
            continue

        rows.append(row)

    df = pd.DataFrame(rows)
    return df


def save_clean_csv() -> pd.DataFrame:
    df = load_clean_dataframe()
    CLEAN_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(CLEAN_PATH, index=False)
    return df


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    df = save_clean_csv()
    print(f"Parsed {len(df)} rows (of 244 source instances) -> {CLEAN_PATH}")
    print(df["region"].value_counts())
    print(df["fire"].value_counts())
