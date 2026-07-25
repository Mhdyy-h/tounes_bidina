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
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS checkpoints (
                id TEXT PRIMARY KEY,
                zone_id TEXT NOT NULL,
                name TEXT NOT NULL,
                type TEXT NOT NULL,
                lat REAL NOT NULL,
                lon REAL NOT NULL,
                geofence_radius_m REAL NOT NULL,
                points_value INTEGER NOT NULL,
                secret TEXT NOT NULL,
                is_approximate_location INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS point_transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tourist_id TEXT NOT NULL,
                checkpoint_id TEXT NOT NULL,
                points INTEGER NOT NULL,
                earned_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_point_tx_tourist
            ON point_transactions (tourist_id, checkpoint_id)
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS rewards_catalog (
                id TEXT PRIMARY KEY,
                zone_id TEXT NOT NULL,
                partner_name TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                points_cost INTEGER NOT NULL,
                is_demo_data INTEGER NOT NULL DEFAULT 1,
                active INTEGER NOT NULL DEFAULT 1
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS reward_redemptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                redemption_code TEXT NOT NULL UNIQUE,
                tourist_id TEXT NOT NULL,
                reward_id TEXT NOT NULL,
                points_spent INTEGER NOT NULL,
                redeemed_at TEXT NOT NULL,
                fulfilled_at TEXT,
                fulfilled_by TEXT
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


# ─── Rewards: Checkpoints ──────────────────────────────────────────────────

def upsert_checkpoint(checkpoint: dict) -> dict:
    """Idempotent - used both for startup seeding and any future admin edits."""
    now = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO checkpoints (
                id, zone_id, name, type, lat, lon, geofence_radius_m,
                points_value, secret, is_approximate_location, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                zone_id = excluded.zone_id,
                name = excluded.name,
                type = excluded.type,
                lat = excluded.lat,
                lon = excluded.lon,
                geofence_radius_m = excluded.geofence_radius_m,
                points_value = excluded.points_value,
                is_approximate_location = excluded.is_approximate_location
            """,
            (
                checkpoint["id"], checkpoint["zone_id"], checkpoint["name"], checkpoint["type"],
                checkpoint["lat"], checkpoint["lon"], checkpoint["geofence_radius_m"],
                checkpoint["points_value"], checkpoint["secret"],
                int(checkpoint.get("is_approximate_location", True)), now,
            ),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM checkpoints WHERE id = ?", (checkpoint["id"],)).fetchone()
        return dict(row)


def list_checkpoints(zone_id: str | None = None) -> list[dict]:
    with get_connection() as conn:
        if zone_id:
            rows = conn.execute(
                "SELECT * FROM checkpoints WHERE zone_id = ? ORDER BY name", (zone_id,)
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM checkpoints ORDER BY zone_id, name").fetchall()
        return [dict(r) for r in rows]


def get_checkpoint(checkpoint_id: str) -> dict | None:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM checkpoints WHERE id = ?", (checkpoint_id,)).fetchone()
        return dict(row) if row else None


# ─── Rewards: Points ledger ─────────────────────────────────────────────────

def record_point_transaction(tourist_id: str, checkpoint_id: str, points: int) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO point_transactions (tourist_id, checkpoint_id, points, earned_at) "
            "VALUES (?, ?, ?, ?)",
            (tourist_id, checkpoint_id, points, now),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM point_transactions WHERE id = ?", (cur.lastrowid,)
        ).fetchone()
        return dict(row)


def last_checkin_at(tourist_id: str, checkpoint_id: str) -> str | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT earned_at FROM point_transactions "
            "WHERE tourist_id = ? AND checkpoint_id = ? ORDER BY earned_at DESC LIMIT 1",
            (tourist_id, checkpoint_id),
        ).fetchone()
        return row["earned_at"] if row else None


def total_points_earned(tourist_id: str) -> int:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT COALESCE(SUM(points), 0) AS total FROM point_transactions WHERE tourist_id = ?",
            (tourist_id,),
        ).fetchone()
        return row["total"]


def total_points_spent(tourist_id: str) -> int:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT COALESCE(SUM(points_spent), 0) AS total FROM reward_redemptions WHERE tourist_id = ?",
            (tourist_id,),
        ).fetchone()
        return row["total"]


def list_transactions(tourist_id: str, limit: int = 20) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM point_transactions WHERE tourist_id = ? "
            "ORDER BY earned_at DESC LIMIT ?",
            (tourist_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]


# ─── Rewards: Catalog & redemptions ────────────────────────────────────────

def upsert_reward(reward: dict) -> dict:
    """Idempotent - used for startup seeding of example partner rewards."""
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO rewards_catalog (
                id, zone_id, partner_name, title, description, points_cost,
                is_demo_data, active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                zone_id = excluded.zone_id,
                partner_name = excluded.partner_name,
                title = excluded.title,
                description = excluded.description,
                points_cost = excluded.points_cost,
                is_demo_data = excluded.is_demo_data,
                active = excluded.active
            """,
            (
                reward["id"], reward["zone_id"], reward["partner_name"], reward["title"],
                reward.get("description"), reward["points_cost"],
                int(reward.get("is_demo_data", True)), int(reward.get("active", True)),
            ),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM rewards_catalog WHERE id = ?", (reward["id"],)).fetchone()
        return dict(row)


def list_rewards(zone_id: str | None = None, active_only: bool = True) -> list[dict]:
    with get_connection() as conn:
        query = "SELECT * FROM rewards_catalog WHERE 1=1"
        params: list = []
        if zone_id:
            query += " AND zone_id = ?"
            params.append(zone_id)
        if active_only:
            query += " AND active = 1"
        query += " ORDER BY points_cost"
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]


def get_reward(reward_id: str) -> dict | None:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM rewards_catalog WHERE id = ?", (reward_id,)).fetchone()
        return dict(row) if row else None


def create_redemption(tourist_id: str, reward_id: str, points_spent: int, redemption_code: str) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO reward_redemptions "
            "(redemption_code, tourist_id, reward_id, points_spent, redeemed_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (redemption_code, tourist_id, reward_id, points_spent, now),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM reward_redemptions WHERE id = ?", (cur.lastrowid,)
        ).fetchone()
        return dict(row)


def get_redemption(code: str) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM reward_redemptions WHERE redemption_code = ?", (code,)
        ).fetchone()
        return dict(row) if row else None


def fulfill_redemption(code: str, fulfilled_by: str | None) -> bool:
    now = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        cur = conn.execute(
            "UPDATE reward_redemptions SET fulfilled_at = ?, fulfilled_by = ? "
            "WHERE redemption_code = ? AND fulfilled_at IS NULL",
            (now, fulfilled_by, code),
        )
        conn.commit()
        return cur.rowcount > 0


def list_redemptions(tourist_id: str) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM reward_redemptions WHERE tourist_id = ? ORDER BY redeemed_at DESC",
            (tourist_id,),
        ).fetchall()
        return [dict(r) for r in rows]
