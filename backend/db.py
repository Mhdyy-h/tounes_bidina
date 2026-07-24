"""
SQLite persistence - the first genuine use case for a database in this project.
Everything else in Tunisia Guardian AI is computed live or cached from external
APIs; hotel operational status is different: it's real data hotels themselves
declare over time, and it must persist across requests and server restarts.
That's exactly the case the original build explicitly deferred a database for
("nothing needs persistence") - now something does.
"""

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "app.db"


@contextmanager
def get_connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def init_db() -> None:
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS hotels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                zone_id TEXT NOT NULL,
                hotel_name TEXT NOT NULL,
                electricity_available INTEGER NOT NULL DEFAULT 1,
                water_available INTEGER NOT NULL DEFAULT 1,
                internet_available INTEGER NOT NULL DEFAULT 1,
                generator_available INTEGER NOT NULL DEFAULT 0,
                battery_backup INTEGER NOT NULL DEFAULT 0,
                solar_panels INTEGER NOT NULL DEFAULT 0,
                remaining_autonomy_hours REAL,
                rooms_available INTEGER,
                contact_email TEXT,
                updated_at TEXT NOT NULL,
                UNIQUE(zone_id, hotel_name)
            )
            """
        )
        conn.commit()


def _row_to_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    for k in ("electricity_available", "water_available", "internet_available",
              "generator_available", "battery_backup", "solar_panels"):
        d[k] = bool(d[k])
    return d


def upsert_hotel(zone_id: str, hotel_name: str, status: dict) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO hotels (
                zone_id, hotel_name, electricity_available, water_available,
                internet_available, generator_available, battery_backup, solar_panels,
                remaining_autonomy_hours, rooms_available, contact_email, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(zone_id, hotel_name) DO UPDATE SET
                electricity_available = excluded.electricity_available,
                water_available = excluded.water_available,
                internet_available = excluded.internet_available,
                generator_available = excluded.generator_available,
                battery_backup = excluded.battery_backup,
                solar_panels = excluded.solar_panels,
                remaining_autonomy_hours = excluded.remaining_autonomy_hours,
                rooms_available = excluded.rooms_available,
                contact_email = excluded.contact_email,
                updated_at = excluded.updated_at
            """,
            (
                zone_id, hotel_name,
                int(status["electricity_available"]), int(status["water_available"]),
                int(status["internet_available"]), int(status["generator_available"]),
                int(status["battery_backup"]), int(status["solar_panels"]),
                status.get("remaining_autonomy_hours"), status.get("rooms_available"),
                status.get("contact_email"), now,
            ),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM hotels WHERE zone_id = ? AND hotel_name = ?", (zone_id, hotel_name)
        ).fetchone()
        return _row_to_dict(row)


def list_hotels(zone_id: str | None = None) -> list[dict]:
    with get_connection() as conn:
        if zone_id:
            rows = conn.execute(
                "SELECT * FROM hotels WHERE zone_id = ? ORDER BY hotel_name", (zone_id,)
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM hotels ORDER BY zone_id, hotel_name").fetchall()
        return [_row_to_dict(r) for r in rows]


def delete_hotel(zone_id: str, hotel_name: str) -> bool:
    with get_connection() as conn:
        cur = conn.execute(
            "DELETE FROM hotels WHERE zone_id = ? AND hotel_name = ?", (zone_id, hotel_name)
        )
        conn.commit()
        return cur.rowcount > 0
