"""
Famma Dhaw (https://famma-dhaw.com) - real-time crowd-sourced electricity outage
reports for Tunisia, covering 376 neighborhoods/municipalities nationwide.

No public/documented API. Their own frontend queries a public Supabase project
directly from client-side JS (visible in the page's own HTML source) using a
"publishable" key - Supabase's term for a key explicitly meant for public client
use, with access governed by the project's Row Level Security policies rather
than being a secret. This module makes the exact same public, read-only query
their own website makes - same request, same public key, just from a Python
backend instead of a browser.

Honesty notes (this is the electricity agent's real data source, replacing the
SIMULATED_OUTAGES dict where a zone maps to real coverage):
- Unofficial, community-voted data. Famma Dhaw's own footer says so explicitly:
  "Données communautaires non officielles - Croisez avec les communiqués STEG."
  Never presented as official grid telemetry.
- No documented schema/contract - if their query shape or response changes,
  this fails to None, never crashes. Same fallback pattern as every other
  external dependency in this project.
- Cached 10 minutes, one request fetches all ~376 zones - a respectful,
  low-frequency client against someone's small community project, not
  infra-grade polling.
- 3 of our 7 zones (Dougga, Bulla Regia, Ichkeul) are archaeological/nature
  sites with no residential neighborhood of their own in Famma Dhaw's data, so
  they're mapped to their nearest tracked municipality. That's an
  approximation, explicitly flagged via `is_exact_location_match`, not the
  status of the exact site. Siliana is the exception among the newer zones -
  Famma Dhaw tracks "Siliana Ville" directly, so that mapping is exact.
"""

import logging

import httpx

from backend.cache import TTLCache

logger = logging.getLogger(__name__)

SUPABASE_URL = "https://njfulpklvqezflxiozhn.supabase.co/rest/v1/zone_board_weighted"
SUPABASE_ANON_KEY = "sb_publishable_C_7rg0jf6-e925Tji5n-qA_mLYruFUp"

# Mirrors famma-dhaw.com's own classify() thresholds exactly, so our status
# labels agree with what a visitor sees on the site itself.
CONTEST_RATIO = 0.9
CONTEST_FLOOR = 4

# zone_id -> (famma_dhaw_slug, is_exact_match)
ZONE_SLUG_MAP: dict[str, tuple[str, bool]] = {
    "ain_draham":  ("ain-draham", True),
    "tabarka":     ("tabarka", True),
    "hammamet":    ("hammamet", True),
    "dougga":      ("teboursouk", False),      # nearest tracked town, ~7km from the ruins
    "bulla_regia": ("jendouba-ville", False),  # nearest tracked town, ~15km from the ruins
    "ichkeul":     ("mateur", False),          # nearest tracked town, adjacent to the lake
    "siliana":     ("siliana-ville", True),    # exact match - "Siliana Ville" is directly tracked
}

_cache = TTLCache(ttl_seconds=600)


def _classify(off_weight: float, on_weight: float, total_count: int) -> str:
    """Mirrors famma-dhaw.com's client-side classify() logic exactly."""
    if total_count == 0:
        return "no_data"
    hi, lo = max(off_weight, on_weight), min(off_weight, on_weight)
    if (off_weight + on_weight) >= CONTEST_FLOOR and hi > 0 and (lo / hi) >= CONTEST_RATIO:
        return "contested"
    return "cut" if off_weight > on_weight else "working"


async def fetch_all_zones() -> dict[str, dict] | None:
    """Returns {slug: raw_record} for all tracked zones, or None on failure."""
    cached = _cache.get("all")
    if cached is not None:
        return cached

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                SUPABASE_URL,
                params={"select": "*"},
                headers={
                    "apikey": SUPABASE_ANON_KEY,
                    "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
                },
            )
            resp.raise_for_status()
            records = resp.json()

        by_slug = {r["slug"]: r for r in records if "slug" in r}
        _cache.set("all", by_slug)
        return by_slug
    except Exception as exc:
        logger.warning("Famma Dhaw fetch failed (%s)", exc)
        return None


async def get_zone_outage_status(zone_id: str) -> dict | None:
    """Returns real outage status for a Tunisia Guardian AI zone, or None if
    unavailable (no mapping for this zone, fetch failed, or slug not found in
    their data) - callers must fall back to simulated data in that case."""
    mapping = ZONE_SLUG_MAP.get(zone_id)
    if mapping is None:
        return None
    slug, is_exact = mapping

    all_zones = await fetch_all_zones()
    if all_zones is None or slug not in all_zones:
        return None

    record = all_zones[slug]
    off_weight = float(record.get("off_weight") or 0)
    on_weight = float(record.get("on_weight") or 0)
    off_count = int(record.get("off_count") or 0)
    on_count = int(record.get("on_count") or 0)
    status = _classify(off_weight, on_weight, off_count + on_count)

    return {
        "status": status,  # "working" | "cut" | "contested" | "no_data"
        "famma_dhaw_name": record.get("name"),
        "famma_dhaw_gov": record.get("gov"),
        "off_count": off_count,
        "on_count": on_count,
        "last_report": record.get("last_report"),
        "is_exact_location_match": is_exact,
    }
