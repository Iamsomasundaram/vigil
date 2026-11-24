"""Redis-or-memory cache backend used by API hardening (F10)."""

from __future__ import annotations

import json
import os
import time
from typing import Any


class CacheBackend:
    def __init__(self, default_ttl: int = 300):
        self.default_ttl = max(1, default_ttl)
        self._mem: dict[str, tuple[float, str]] = {}
        self._redis = None

        redis_url = os.getenv("REDIS_URL", "").strip()
        if redis_url:
            try:
                import redis

                self._redis = redis.Redis.from_url(redis_url, decode_responses=True)
                self._redis.ping()
            except Exception:
                self._redis = None

    def get(self, key: str) -> dict[str, Any] | None:
        if self._redis is not None:
            try:
                raw = self._redis.get(key)
                if raw is None:
                    return None
                return json.loads(raw)
            except Exception:
                return None

        row = self._mem.get(key)
        if not row:
            return None
        expires_at, raw = row
        if expires_at <= time.time():
            self._mem.pop(key, None)
            return None
        return json.loads(raw)

    def set(self, key: str, payload: dict[str, Any], ttl_seconds: int | None = None) -> None:
        ttl = max(1, ttl_seconds or self.default_ttl)
        raw = json.dumps(payload)

        if self._redis is not None:
            try:
                self._redis.setex(key, ttl, raw)
                return
            except Exception:
                pass

        self._mem[key] = (time.time() + ttl, raw)

    def ttl(self, key: str) -> int:
        if self._redis is not None:
            try:
                t = self._redis.ttl(key)
                return int(max(0, t if t is not None else 0))
            except Exception:
                return 0
        row = self._mem.get(key)
        if not row:
            return 0
        return max(0, int(row[0] - time.time()))
