"""
vigil/hardening.py — API hardening (F10): optional API-key auth, rate limit, response cache.

State lives at module level on purpose (single process, learning project); tests
adjust it directly, e.g. ``hardening._API_KEYS = {"k"}``.  Registered as HTTP
middleware in ``vigil/api.py``.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from fastapi import Request
from fastapi.responses import JSONResponse
from typing import Any
from vigil.cache import CacheBackend


# ─── HARDENING (F10): AUTH + RATE LIMIT + RESPONSE CACHE ───────────────────

_API_KEYS = {k.strip() for k in os.getenv("VIGIL_API_KEYS", "").split(",") if k.strip()}
_RATE_PER_MIN = int(os.getenv("VIGIL_RATE_PER_MIN", "60"))
_CACHE_TTL = int(os.getenv("VIGIL_CACHE_TTL", "300"))
_CACHE = CacheBackend(default_ttl=_CACHE_TTL)
_RATE_STATE: dict[str, dict[str, float]] = {}


def _is_protected_path(path: str, method: str) -> bool:
    if method.upper() != "POST":
        return False
    protected_prefixes = (
        "/l0/", "/l1/", "/l2/", "/l3/", "/l4/", "/l4b/", "/l5/",
        "/r1/", "/r2/", "/r4/", "/inference/compare", "/foundations/prompt-compare",
    )
    return path.startswith(protected_prefixes)


def _check_rate(identity: str) -> bool:
    now = time.time()
    state = _RATE_STATE.setdefault(identity, {"tokens": float(_RATE_PER_MIN), "last": now})
    elapsed = max(0.0, now - state["last"])
    refill_per_sec = _RATE_PER_MIN / 60.0
    state["tokens"] = min(float(_RATE_PER_MIN), state["tokens"] + elapsed * refill_per_sec)
    state["last"] = now
    if state["tokens"] < 1.0:
        return False
    state["tokens"] -= 1.0
    return True


def _cache_key(namespace: str, payload: dict[str, Any]) -> str:
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    raw = json.dumps({"ns": namespace, "model": model, "payload": payload}, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


async def enforce_hardening(request: Request, call_next):
    path = request.url.path
    method = request.method.upper()

    if _is_protected_path(path, method):
        api_key = request.headers.get("x-api-key")
        if _API_KEYS and api_key not in _API_KEYS:
            return JSONResponse(status_code=401, content={"detail": "Missing or invalid API key"})

        identity = api_key or (request.client.host if request.client else "unknown")
        if not _check_rate(identity):
            return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded"})

    return await call_next(request)
