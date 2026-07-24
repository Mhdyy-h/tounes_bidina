"""
Minimal in-memory TTL cache for external API responses. Not a general-purpose
cache - just enough to stop re-fetching weather/FIRMS data on every single
poll for the same near-identical coordinates a few seconds apart.
"""

import time
from typing import Any


class TTLCache:
    def __init__(self, ttl_seconds: float):
        self.ttl_seconds = ttl_seconds
        self._store: dict[Any, tuple[float, Any]] = {}

    def get(self, key: Any) -> Any | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        expires_at, value = entry
        if time.monotonic() >= expires_at:
            del self._store[key]
            return None
        return value

    def set(self, key: Any, value: Any) -> None:
        self._store[key] = (time.monotonic() + self.ttl_seconds, value)
