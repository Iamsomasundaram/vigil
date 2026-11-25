"""
vigil/routers/system.py — System endpoints: health, API info and rate-limit diagnostics.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from vigil import hardening
from vigil.schemas import HealthResponse

router = APIRouter()


# ─── HEALTH ───────────────────────────────────────────────────────────────────

@router.get("/health", response_model=HealthResponse, tags=["system"])
def health():
    """Liveness check — returns 200 if the service is up."""
    return {"status": "ok", "service": "vigil", "version": "0.1.0"}


@router.get("/", tags=["system"])
def root():
    """API info and available endpoints."""
    return {
        "service": "Vigil — Autonomous CVE Intelligence Agent",
        "levels": {
            "L0": "POST /l0/analyse — single LLM call",
            "L1": "POST /l1/analyse — chained prompts + structured output",
            "L2": "POST /l2/analyse — parallel agents + moderator",
            "L3": "POST /l3/analyse — conditional routing",
            "L4": "POST /l4/analyse — tool use (live NVD + EPSS APIs)",
            "L4b": "POST /l4b/image · /l4b/pdf — multimodal (vision + document parsing)",
            "L5": "POST /l5/analyse — memory + feedback loop (PostgreSQL)",
            "L6": "POST /l6/monitor/start — autonomous monitoring (kill switch: /l6/monitor/stop)",
        },
        "foundations": {
            "F4": "POST /foundations/tokenize — token report + context economics",
            "F6": "POST /foundations/prompt-compare — zero/few-shot/CoT/self-consistency",
            "F11": "POST /foundations/retrieval-lab — chunking/index quality and ranked hits",
            "F12": "POST /foundations/retrieval-eval — Recall@k, MRR, nDCG across settings",
            "F13": "POST /foundations/factuality-check — claim support and abstain signal",
            "F14": "GET /foundations/prompt-versions · POST /foundations/prompt-versions/compare",
            "F15": "POST /foundations/privacy/redact — detect and redact sensitive content",
            "F8": "GET /l4/tools?source=inline|mcp — discover tool definitions",
        },
        "themes": {
            "T1": "POST /themes/incident/analyse — incident response ops planning",
        },
        "docs": "/docs",
    }


@router.get("/admin/ratelimit", tags=["system"])
def admin_ratelimit(request: Request):
    """Inspect in-memory rate bucket state (local diagnostics)."""
    if hardening._API_KEYS:
        api_key = request.headers.get("x-api-key")
        if api_key not in hardening._API_KEYS:
            raise HTTPException(status_code=401, detail="Missing or invalid API key")
    return {"rate_per_min": hardening._RATE_PER_MIN, "buckets": hardening._RATE_STATE}
