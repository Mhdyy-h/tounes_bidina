"""
Tourist rewards engine: QR check-ins at monuments/hotels/airports award
points, redeemable for partner perks. Pure functions over checkpoint/ledger
data from backend/db.py - no direct DB/HTTP access, matching the rest of
this project's *_service.py modules.

Anti-fraud model, deliberately simple and honestly scoped:
  - The QR each checkpoint prints encodes a STATIC signed URL (checkpoint_id
    + an HMAC signature keyed by that checkpoint's server-generated secret).
    This is intentional, not a shortcut: a real monument/park checkpoint is a
    printed poster with no power or connectivity, so the code can't rotate
    on a timer. The signature's only job is to stop someone hand-editing a
    URL to claim a checkpoint_id (and its points value) they never scanned -
    it does NOT stop someone photographing the QR and sharing it, because...
  - ...the actual anti-fraud control is the geofence: check-in also requires
    the browser's live GPS position within the checkpoint's
    geofence_radius_m. A shared photo only helps someone who is ALSO
    physically there, which is a real visit, not fraud.
  - A per-tourist-per-checkpoint cooldown (COOLDOWN_HOURS) stops farming the
    same checkpoint repeatedly within one visit.
No real partner has committed to any reward in rewards_catalog_seed.json
yet - every seeded row is marked is_demo_data so nothing here is presented
as a real, honored offer until the ministry/hotels actually opt in.
"""

import hashlib
import hmac
import math
import secrets
from datetime import datetime, timezone

COOLDOWN_HOURS = 20.0


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6_371_000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def generate_secret() -> str:
    return secrets.token_hex(16)


def sign_checkpoint(checkpoint_id: str, secret: str) -> str:
    return hmac.new(secret.encode(), checkpoint_id.encode(), hashlib.sha256).hexdigest()[:16]


def verify_signature(checkpoint_id: str, secret: str, signature: str) -> bool:
    expected = sign_checkpoint(checkpoint_id, secret)
    return hmac.compare_digest(expected, signature)


def build_checkin_path(checkpoint_id: str, secret: str) -> str:
    """Relative path encoded in the checkpoint's printed QR code."""
    sig = sign_checkpoint(checkpoint_id, secret)
    return f"/checkin/{checkpoint_id}?sig={sig}"


def check_geofence(
    checkpoint: dict, lat: float, lon: float
) -> tuple[bool, float]:
    """Returns (within_radius, distance_m)."""
    distance_m = haversine_m(checkpoint["lat"], checkpoint["lon"], lat, lon)
    return distance_m <= checkpoint["geofence_radius_m"], distance_m


def check_cooldown(last_checkin_iso: str | None) -> tuple[bool, float | None]:
    """Returns (allowed, hours_remaining_if_blocked)."""
    if last_checkin_iso is None:
        return True, None
    last = datetime.fromisoformat(last_checkin_iso)
    elapsed_hours = (datetime.now(timezone.utc) - last).total_seconds() / 3600.0
    if elapsed_hours >= COOLDOWN_HOURS:
        return True, None
    return False, round(COOLDOWN_HOURS - elapsed_hours, 1)


def generate_redemption_code() -> str:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O/1/I ambiguity
    return "".join(secrets.choice(alphabet) for _ in range(8))
