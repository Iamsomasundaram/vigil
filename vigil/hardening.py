"""
vigil/hardening.py — API hardening (F10): auth, scopes, rate limit, request limits, cache.

Rules, in the order the middleware applies them:

1. Request size   body over ``VIGIL_MAX_BODY_BYTES`` (uploads: ``VIGIL_MAX_UPLOAD_BYTES``) -> 413;
                  chunked bodies without a length -> 411.
2. Authentication deny by default: every route except ``/health`` (and the docs pages in
                  dev) needs a key once keys are configured.  Missing/invalid -> 401.
3. Scope          ``read`` < ``run`` < ``admin``.  GET needs read, anything that can spend
                  LLM money needs run, kill switch / budgets / diagnostics need admin -> 403.
4. Rate limit     token bucket per caller (key name, or client IP for anonymous / failed auth).
5. Concurrency    at most ``VIGIL_MAX_CONCURRENCY`` requests that can call an LLM at once -> 503.

Modes (``VIGIL_ENV``):  ``dev`` (default) is open when no keys are set, with a startup
warning.  ``prod`` refuses to start without keys and also protects the docs pages.

State lives at module level on purpose (single process, learning project); tests adjust it
directly, e.g. ``hardening._API_KEYS = hardening.parse_api_keys("alice:k1:run")``.
Registered as HTTP middleware in ``vigil/api.py``.  For real production, put OAuth2/OIDC at
a gateway in front of this service and treat these keys as service-to-service credentials.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import time
from fastapi import Request
from fastapi.responses import JSONResponse
from typing import Any
from vigil.cache import CacheBackend

log = logging.getLogger("vigil.hardening")

SCOPES = ("read", "run", "admin")  # each scope includes the ones before it
_DEV_CORS_DEFAULT = "http://localhost:8501,http://127.0.0.1:8501"  # Streamlit UI


# ─── CONFIGURATION ───────────────────────────────────────────────────────────

def parse_api_keys(raw: str) -> dict[str, tuple[str, str]]:
    """Parse ``VIGIL_API_KEYS`` into ``{key: (name, scope)}``.

    Entries are comma-separated.  ``name:key:scope`` gives a named key with a scope; a bare
    ``key`` is a single-operator key named ``key<n>`` with admin scope (backwards compatible).
    """
    keys: dict[str, tuple[str, str]] = {}
    for i, entry in enumerate(e.strip() for e in raw.split(",")):
        if not entry:
            continue
        parts = entry.split(":")
        if len(parts) == 1:
            name, key, scope = f"key{i}", parts[0], "admin"
        elif len(parts) == 3:
            name, key, scope = parts
        else:
            raise ValueError("VIGIL_API_KEYS entries are 'key' or 'name:key:scope'")
        if scope not in SCOPES:
            raise ValueError(f"VIGIL_API_KEYS scope must be one of {SCOPES}, got {scope!r}")
        if not name or not key:
            raise ValueError("VIGIL_API_KEYS name and key must not be empty")
        if key in keys:
            raise ValueError("VIGIL_API_KEYS contains a duplicate key")
        keys[key] = (name, scope)
    return keys


def parse_cors_origins(raw: str) -> list[str]:
    origins = [o.strip() for o in raw.split(",") if o.strip()]
    if "*" in origins:
        raise ValueError("VIGIL_CORS_ORIGINS must list explicit origins; '*' is not allowed")
    return origins


_ENV = os.getenv("VIGIL_ENV", "dev").strip().lower()
if _ENV not in ("dev", "prod"):
    raise ValueError("VIGIL_ENV must be 'dev' or 'prod'")

_API_KEYS = parse_api_keys(os.getenv("VIGIL_API_KEYS", ""))
_CORS_ORIGINS = parse_cors_origins(
    os.getenv("VIGIL_CORS_ORIGINS", _DEV_CORS_DEFAULT if _ENV == "dev" else "")
)
_RATE_PER_MIN = int(os.getenv("VIGIL_RATE_PER_MIN", "60"))
_CACHE_TTL = int(os.getenv("VIGIL_CACHE_TTL", "300"))
_MAX_BODY_BYTES = int(os.getenv("VIGIL_MAX_BODY_BYTES", "1000000"))
_MAX_UPLOAD_BYTES = int(os.getenv("VIGIL_MAX_UPLOAD_BYTES", "15000000"))
_MAX_CONCURRENCY = int(os.getenv("VIGIL_MAX_CONCURRENCY", "8"))
_CACHE = CacheBackend(default_ttl=_CACHE_TTL)
_RATE_STATE: dict[str, dict[str, float]] = {}
_IN_FLIGHT = 0

_PUBLIC_PATHS = {"/health"}
_DOC_PATHS = {"/docs", "/redoc", "/openapi.json"}
_ADMIN_PATHS = {"/l6/monitor/start", "/l6/monitor/stop", "/r5/budget"}
_ADMIN_PREFIXES = ("/admin/",)
_RUN_GET_PATHS = {"/l1/stream"}  # a GET that still calls the LLM
_BODY_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def validate_config() -> None:
    """Run at startup (FastAPI lifespan). ``prod`` fails closed; ``dev`` warns loudly."""
    if not _API_KEYS:
        if _ENV == "prod":
            raise RuntimeError(
                "VIGIL_ENV=prod requires VIGIL_API_KEYS (e.g. 'ops:<long-random-key>:admin'). "
                "Refusing to start an unauthenticated API."
            )
        log.warning(
            "VIGIL_ENV=dev and VIGIL_API_KEYS is empty: the API is OPEN (no auth). "
            "Fine for local learning; never expose this port. Set VIGIL_ENV=prod to enforce auth."
        )


# ─── RULES ───────────────────────────────────────────────────────────────────

def required_scope(path: str, method: str) -> str | None:
    """Scope a request needs, or None when the route is public."""
    method = method.upper()
    if path in _PUBLIC_PATHS or method == "OPTIONS":
        return None
    if path in _DOC_PATHS and _ENV == "dev":
        return None
    if path in _ADMIN_PATHS or path.startswith(_ADMIN_PREFIXES):
        return "admin"
    if method in ("GET", "HEAD") and path not in _RUN_GET_PATHS:
        return "read"
    return "run"


def _lookup_key(presented: str | None) -> tuple[str, str] | None:
    """Constant-time key check: compares against every key, never exits early."""
    if not presented:
        return None
    match = None
    for key, principal in _API_KEYS.items():
        if hmac.compare_digest(presented.encode(), key.encode()):
            match = principal
    return match


def _has_scope(granted: str, needed: str) -> bool:
    return SCOPES.index(granted) >= SCOPES.index(needed)


def _body_limit(path: str) -> int:
    return _MAX_UPLOAD_BYTES if path.startswith("/l4b/") else _MAX_BODY_BYTES


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


def _reject(status: int, detail: str, **headers: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"detail": detail}, headers=headers or None)


# ─── MIDDLEWARE ──────────────────────────────────────────────────────────────

async def enforce_hardening(request: Request, call_next):
    global _IN_FLIGHT
    path = request.url.path
    method = request.method.upper()
    needed = required_scope(path, method)
    if needed is None:
        return await call_next(request)

    # 1. request size
    if method in _BODY_METHODS:
        length = request.headers.get("content-length")
        if length is None:
            if "chunked" in request.headers.get("transfer-encoding", "").lower():
                return _reject(411, "Content-Length required")
        else:
            try:
                too_big = int(length) > _body_limit(path)
            except ValueError:
                return _reject(400, "Invalid Content-Length")
            if too_big:
                return _reject(413, "Request body too large")

    # 2. authentication (deny by default once keys exist; prod with no keys denies all)
    host = request.client.host if request.client else "unknown"
    if _API_KEYS or _ENV == "prod":
        principal = _lookup_key(request.headers.get("x-api-key"))
        if principal is None:
            # failed attempts are rate limited per IP, so keys cannot be brute-forced
            if not _check_rate(f"anon:{host}"):
                return _reject(429, "Rate limit exceeded")
            return _reject(401, "Missing or invalid API key")
        name, scope = principal
        # 3. scope
        if not _has_scope(scope, needed):
            return _reject(403, f"API key scope '{scope}' cannot call this route (needs '{needed}')")
        identity = name
    else:
        identity = f"anon:{host}"  # dev mode, no keys configured: open

    # 4. rate limit (calls that can spend money or change state)
    if needed != "read" and not _check_rate(identity):
        return _reject(429, "Rate limit exceeded")

    # 5. concurrency cap on calls that can reach an LLM (released when headers are sent)
    if needed == "read":
        return await call_next(request)
    if _IN_FLIGHT >= _MAX_CONCURRENCY:
        return _reject(503, "Server busy, retry shortly", **{"Retry-After": "2"})
    _IN_FLIGHT += 1
    try:
        return await call_next(request)
    finally:
        _IN_FLIGHT -= 1
