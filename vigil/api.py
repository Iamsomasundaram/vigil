"""
vigil/api.py — FastAPI Service
================================
A thin HTTP wrapper around the level scripts.

This lets you call Vigil over the network instead of the CLI,
which is necessary for Docker, testing, and future frontends.

Endpoints:
  GET  /health                         — liveness check
  GET  /                               — API info
  POST /l0/analyse                     — single LLM call
  POST /l1/analyse                     — 3-step chain
  POST /l2/analyse                     — parallel agents + moderator
  POST /l3/analyse                     — conditional routing
  POST /l4/analyse                     — tool use (live NVD + EPSS)
  POST /l5/analyse                     — memory + feedback loop
  POST /l5/feedback                    — record outcome
  GET  /l5/history/{cve_id}            — analysis history
  POST /l6/watchlist                   — add CVE to autonomous monitor
  DELETE /l6/watchlist/{cve_id}        — remove CVE from monitor
  GET  /l6/watchlist                   — list monitored CVEs
  POST /l6/scan                        — trigger one manual scan
  GET  /l6/alerts                      — get generated alerts
  POST /l6/alerts/{id}/acknowledge     — acknowledge an alert
  POST /l6/monitor/start               — start autonomous loop
  POST /l6/monitor/stop                — kill switch
  GET  /l6/monitor/status              — loop running? last scan?

Layout:
  vigil/api.py        app, lifespan, middleware, router registration (this file)
  vigil/hardening.py  optional API-key auth, rate limit, response cache
  vigil/schemas.py    request/response models for the API
  vigil/routers/      one module per area: system, levels, reliability, foundations,
                      architectures, extensions

Swagger UI (auto-generated):  http://localhost:8000/docs
ReDoc UI (auto-generated):    http://localhost:8000/redoc
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from fastapi import FastAPI
from vigil import hardening
from vigil.routers import (
    architectures,
    extensions,
    foundations,
    levels,
    reliability,
    system,
)


# ─── LIFESPAN ─────────────────────────────────────────────────────────────────
# FastAPI lifespan manages startup and shutdown events.
# On shutdown, we stop the autonomous monitor so the background task is
# cancelled cleanly — no orphaned asyncio.Tasks when the container stops.

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield  # App is running
    # Shutdown: stop the autonomous monitor if it's running
    try:
        from levels.l6_autonomous import stop_monitor, is_running
        if is_running():
            await stop_monitor()
    except Exception:
        pass


app = FastAPI(
    title="Vigil",
    description="Autonomous CVE Intelligence & Remediation Agent — GenAI Learning Project",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.middleware("http")(hardening.enforce_hardening)

for _router in (
    system.router,
    levels.router,
    reliability.router,
    foundations.router,
    architectures.router,
    extensions.router,
):
    app.include_router(_router)
