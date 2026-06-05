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

Swagger UI (auto-generated):  http://localhost:8000/docs
ReDoc UI (auto-generated):    http://localhost:8000/redoc
"""

from __future__ import annotations

import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field


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


# ─── REQUEST / RESPONSE SCHEMAS ───────────────────────────────────────────────

class CVERequest(BaseModel):
    cve_id: str = Field(
        default="CVE-2021-44228",
        description="CVE identifier to analyse",
        examples=["CVE-2021-44228", "CVE-2023-44487", "CVE-2022-22965"],
    )


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str


# ─── RESPONSE MODELS ──────────────────────────────────────────────────────────
# Defining response models here gives Swagger full schema documentation
# for every endpoint — learners can see exactly what each level returns
# before they call it.

class TokenUsage(BaseModel):
    """Token consumption and estimated cost for one level run."""
    prompt_tokens:      int
    completion_tokens:  int
    total_tokens:       int
    estimated_cost_usd: float = Field(description="Estimated cost in USD (gpt-4o-mini pricing)")

class L0Response(BaseModel):
    cve_id:      str
    level:       int
    concept:     str
    elapsed_ms:  int
    explanation: str
    token_usage: TokenUsage

class L1Response(BaseModel):
    cve_id:      str
    level:       int
    concept:     str
    elapsed_ms:  int
    steps:       dict  # 1_summary, 2_risk, 3_remediation
    token_usage: TokenUsage

class L2Response(BaseModel):
    cve_id:        str
    level:         int
    concept:       str
    elapsed_ms:    int
    agent_reports: dict
    verdict:       dict
    token_usage:   TokenUsage

class L3Response(BaseModel):
    cve_id:      str
    level:       int
    concept:     str
    elapsed_ms:  int
    routing:     dict
    result:      dict
    token_usage: TokenUsage

class L4Response(BaseModel):
    cve_id:      str
    level:       int
    concept:     str
    elapsed_ms:  int
    tool_calls:  list
    analysis:    dict
    token_usage: TokenUsage

class L5Response(BaseModel):
    cve_id:               str
    level:                int
    concept:              str
    elapsed_ms:           int
    analysis:             dict
    tool_calls:           list
    prior_history_count:  int
    token_usage:          TokenUsage

class WatchlistEntry(BaseModel):
    cve_id:       str
    added_at:     str
    last_scanned: str | None

class AlertEntry(BaseModel):
    id:                 int
    cve_id:             str
    alert_type:         str
    severity:           str
    summary:            str
    recommended_action: str
    epss_now:           float
    cvss_now:           float
    acknowledged:       bool
    created_at:         str


# ─── HEALTH ───────────────────────────────────────────────────────────────────

@app.get("/health", response_model=HealthResponse, tags=["system"])
def health():
    """Liveness check — returns 200 if the service is up."""
    return {"status": "ok", "service": "vigil", "version": "0.1.0"}


@app.get("/", tags=["system"])
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
            "L5": "POST /l5/analyse — memory + feedback loop (PostgreSQL)",
            "L6": "POST /l6/monitor/start — autonomous monitoring (kill switch: /l6/monitor/stop)",
        },
        "docs": "/docs",
    }


# ─── LEVEL 0 ──────────────────────────────────────────────────────────────────
# Concept: single LLM call, free-form text response

@app.post("/l0/analyse", response_model=L0Response, tags=["levels"])
def analyse_l0(req: CVERequest):
    """
    Level 0 — Single LLM Call.

    The simplest possible analysis: one prompt, one text response.
    Teaches: system prompts, model parameters, basic API call.
    """
    # Import here (not at module top) so startup stays fast.
    # Each level file is standalone; we just call its core function.
    try:
        from levels.l0_single_call import explain_cve, get_usage
        start = time.perf_counter()
        explanation = explain_cve(req.cve_id)
        elapsed_ms  = int((time.perf_counter() - start) * 1000)
        return {
            "cve_id":      req.cve_id,
            "level":       0,
            "concept":     "single LLM call",
            "elapsed_ms":  elapsed_ms,
            "explanation": explanation,
            "token_usage": get_usage(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── LEVEL 1 ──────────────────────────────────────────────────────────────────
# Concept: prompt chaining + structured output (Pydantic)

@app.post("/l1/analyse", response_model=L1Response, tags=["levels"])
def analyse_l1(req: CVERequest):
    """
    Level 1 — Prompt Chain + Structured Output.

    Three sequential LLM calls: summarise → assess risk → remediation plan.
    Each step's output feeds the next. All outputs are typed Pydantic objects.
    Teaches: chaining, structured output, context accumulation.
    """
    try:
        from levels.l1_chain import step1_summarise, step2_assess_risk, step3_remediation, get_usage as l1_get_usage
        start = time.perf_counter()

        summary = step1_summarise(req.cve_id)   # also calls _reset_usage()
        risk    = step2_assess_risk(summary)
        plan    = step3_remediation(summary, risk)

        elapsed_ms = int((time.perf_counter() - start) * 1000)
        return {
            "cve_id":     req.cve_id,
            "level":      1,
            "concept":    "prompt chain + structured output",
            "elapsed_ms": elapsed_ms,
            "steps": {
                "1_summary":     summary.model_dump(),
                "2_risk":        risk.model_dump(),
                "3_remediation": plan.model_dump(),
            },
            "token_usage": l1_get_usage(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── LEVEL 2 ──────────────────────────────────────────────────────────────────
# Concept: parallel async fan-out + synthesis

@app.post("/l2/analyse", response_model=L2Response, tags=["levels"])
async def analyse_l2(req: CVERequest):
    """
    Level 2 — Parallel Agent Fan-out.

    Four specialist agents run concurrently, then a moderator synthesises.
    Teaches: asyncio, parallel execution, multi-agent patterns, aggregation.
    """
    try:
        from levels.l2_parallel import analyse_cve, get_usage as l2_get_usage
        start = time.perf_counter()

        agent_reports, verdict = await analyse_cve(req.cve_id)

        elapsed_ms = int((time.perf_counter() - start) * 1000)
        return {
            "cve_id":     req.cve_id,
            "level":      2,
            "concept":    "parallel agent fan-out + synthesis",
            "elapsed_ms": elapsed_ms,
            "agent_reports": {
                name: report.model_dump()
                for name, report in agent_reports.items()
            },
            "verdict":     verdict.model_dump(),
            "token_usage": l2_get_usage(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── LEVEL 3 ──────────────────────────────────────────────────────────────────
# Concept: conditional routing — LLM decides which pipeline to run

@app.post("/l3/analyse", response_model=L3Response, tags=["levels"])
async def analyse_l3(req: CVERequest):
    """
    Level 3 — Conditional Routing.

    A router agent classifies the CVE into one of four tracks, then the
    matching pipeline executes. The LLM's output controls program flow.
    Teaches: router pattern, track-based dispatch, LLM as control flow.
    """
    try:
        from levels.l3_routing import analyse_cve as analyse_cve_l3, get_usage as l3_get_usage
        start = time.perf_counter()

        routing, result = await analyse_cve_l3(req.cve_id)

        elapsed_ms = int((time.perf_counter() - start) * 1000)
        return {
            "cve_id":      req.cve_id,
            "level":       3,
            "concept":     "conditional routing",
            "elapsed_ms":  elapsed_ms,
            "routing":     routing.model_dump(),
            "result":      result.model_dump(),
            "token_usage": l3_get_usage(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── LEVEL 4 ──────────────────────────────────────────────────────────────────
# Concept: tool use — agent calls real external APIs (NVD + EPSS)

@app.post("/l4/analyse", response_model=L4Response, tags=["levels"])
async def analyse_l4(req: CVERequest):
    """
    Level 4 — Tool Use (Grounded Analysis).

    The agent calls the NVD API and EPSS API in a tool-calling loop.
    Analysis is grounded in live data, not model training memory.
    Teaches: tool definitions, the ReAct loop, grounding vs hallucination.
    """
    try:
        from levels.l4_tool_use import analyse_cve as analyse_cve_l4, get_usage as l4_get_usage
        start = time.perf_counter()

        analysis, tool_log = await analyse_cve_l4(req.cve_id)

        elapsed_ms = int((time.perf_counter() - start) * 1000)
        return {
            "cve_id":      req.cve_id,
            "level":       4,
            "concept":     "tool use — grounded analysis via live APIs",
            "elapsed_ms":  elapsed_ms,
            "tool_calls":  tool_log,
            "analysis":    analysis.model_dump(),
            "token_usage": l4_get_usage(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── LEVEL 5 ──────────────────────────────────────────────────────────────────
# Concept: memory + feedback loops — agent recalls history, stores results,
#          and improves recommendations based on what happened after past analyses

class FeedbackRequest(BaseModel):
    cve_id:  str = Field(examples=["CVE-2021-44228"])
    status:  str = Field(
        description="patched | dismissed | in_progress | still_vulnerable | monitoring",
        examples=["patched"],
    )
    notes:   str = Field(default="", description="Optional context about the action taken")


@app.post("/l5/analyse", response_model=L5Response, tags=["levels"])
async def analyse_l5(req: CVERequest):
    """
    Level 5 — Memory & Feedback Loops.

    Recalls prior analyses from PostgreSQL, injects them into the agent's
    context, then stores the new result. Past feedback directly shapes
    current recommendations.
    Teaches: persistent memory, context injection, feedback loops.
    """
    try:
        from levels.l5_memory import analyse_cve as analyse_cve_l5, get_usage as l5_get_usage
        start = time.perf_counter()

        analysis, tool_log, history = await analyse_cve_l5(req.cve_id)

        elapsed_ms = int((time.perf_counter() - start) * 1000)
        return {
            "cve_id":              req.cve_id,
            "level":               5,
            "concept":             "memory + feedback loops",
            "elapsed_ms":          elapsed_ms,
            "analysis":            analysis.model_dump(),
            "tool_calls":          tool_log,
            "prior_history_count": len(history),
            "token_usage":         l5_get_usage(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/l5/feedback", tags=["levels"])
async def feedback_l5(req: FeedbackRequest):
    """
    Record what happened after a Level 5 analysis recommendation.

    This closes the feedback loop — the next analysis of this CVE will
    read this feedback and adjust its recommendation accordingly.
    """
    try:
        from levels.l5_memory import record_feedback
        await record_feedback(req.cve_id, req.status, req.notes)
        return {
            "recorded": True,
            "cve_id":   req.cve_id,
            "status":   req.status,
            "message":  f"Feedback stored. Next analysis of {req.cve_id} will reflect this outcome.",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/l5/history/{cve_id}", tags=["levels"])
async def history_l5(cve_id: str):
    """
    Retrieve the full analysis history for a CVE from memory.

    Shows every past analysis and any feedback recorded for each.
    Useful for auditing the agent's decision trail over time.
    """
    try:
        from levels.l5_memory import get_cve_history
        history = await get_cve_history(cve_id)
        return {
            "cve_id":        cve_id,
            "analysis_count": len(history),
            "history":       [
                {
                    "id":              row["id"],
                    "created_at":      row["created_at"].isoformat() if hasattr(row["created_at"], "isoformat") else str(row["created_at"]),
                    "result":          row["result"] if isinstance(row["result"], dict) else {},
                    "feedback_status": row.get("feedback_status"),
                    "feedback_notes":  row.get("feedback_notes"),
                }
                for row in history
            ],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── LEVEL 6 ──────────────────────────────────────────────────────────────────
# Concept: fully autonomous monitoring — the agent acts without being asked.
#
# Seven endpoints covering the full autonomous lifecycle:
#   Watchlist management → manual scan → alerts → monitor start/stop/status

class WatchlistRequest(BaseModel):
    cve_id: str = Field(examples=["CVE-2021-44228"])


class AcknowledgeRequest(BaseModel):
    acknowledged_by: str = Field(default="api", examples=["security-team"])


@app.post("/l6/watchlist", tags=["levels"])
async def add_to_watchlist_l6(req: WatchlistRequest):
    """Add a CVE to the autonomous monitoring watchlist."""
    try:
        import asyncpg
        from levels.l6_autonomous import init_db_l6, add_to_watchlist
        import os
        conn = await asyncpg.connect(os.getenv("DATABASE_URL", "postgresql://vigil:vigil@db:5432/vigil"))
        try:
            await init_db_l6(conn)
            newly_added = await add_to_watchlist(conn, req.cve_id)
            return {"cve_id": req.cve_id, "status": "added" if newly_added else "already_watching"}
        finally:
            await conn.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/l6/watchlist/{cve_id}", tags=["levels"])
async def remove_from_watchlist_l6(cve_id: str):
    """Remove a CVE from the watchlist (soft delete — history is preserved)."""
    try:
        import asyncpg
        from levels.l6_autonomous import init_db_l6, remove_from_watchlist
        import os
        conn = await asyncpg.connect(os.getenv("DATABASE_URL", "postgresql://vigil:vigil@db:5432/vigil"))
        try:
            await init_db_l6(conn)
            await remove_from_watchlist(conn, cve_id)
            return {"cve_id": cve_id, "status": "removed"}
        finally:
            await conn.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/l6/watchlist", tags=["levels"])
async def get_watchlist_l6():
    """List all CVEs currently being autonomously monitored."""
    try:
        import asyncpg
        from levels.l6_autonomous import init_db_l6, get_watchlist
        import os
        conn = await asyncpg.connect(os.getenv("DATABASE_URL", "postgresql://vigil:vigil@db:5432/vigil"))
        try:
            await init_db_l6(conn)
            watchlist = await get_watchlist(conn)
            return {
                "count": len(watchlist),
                "watchlist": [
                    {
                        "cve_id":       row["cve_id"],
                        "added_at":     row["added_at"].isoformat(),
                        "last_scanned": row["last_scanned"].isoformat() if row["last_scanned"] else None,
                    }
                    for row in watchlist
                ],
            }
        finally:
            await conn.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/l6/scan", tags=["levels"])
async def manual_scan_l6():
    """
    Trigger one immediate scan of all watched CVEs.

    Same logic as the autonomous loop's tick, but fired on demand.
    Useful for testing without waiting for the next scheduled interval.
    """
    try:
        from levels.l6_autonomous import scan_all_once
        import os
        result = await scan_all_once(os.getenv("DATABASE_URL", "postgresql://vigil:vigil@db:5432/vigil"))
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/l6/alerts", tags=["levels"])
async def get_alerts_l6(unacknowledged_only: bool = False):
    """
    Retrieve alerts generated by the autonomous monitor.

    Set unacknowledged_only=true to see only alerts that need human review.
    """
    try:
        import asyncpg
        from levels.l6_autonomous import init_db_l6, get_alerts
        import os
        conn = await asyncpg.connect(os.getenv("DATABASE_URL", "postgresql://vigil:vigil@db:5432/vigil"))
        try:
            await init_db_l6(conn)
            alerts = await get_alerts(conn, unacknowledged_only=unacknowledged_only)
            return {
                "count": len(alerts),
                "alerts": [
                    {
                        "id":                 row["id"],
                        "cve_id":             row["cve_id"],
                        "alert_type":         row["alert_type"],
                        "severity":           row["severity"],
                        "summary":            row["summary"],
                        "recommended_action": row["recommended_action"],
                        "epss_now":           row["epss_now"],
                        "cvss_now":           row["cvss_now"],
                        "acknowledged":       row["acknowledged"],
                        "created_at":         row["created_at"].isoformat(),
                    }
                    for row in alerts
                ],
            }
        finally:
            await conn.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/l6/alerts/{alert_id}/acknowledge", tags=["levels"])
async def acknowledge_alert_l6(alert_id: int, req: AcknowledgeRequest):
    """
    Acknowledge an alert — mark it as reviewed by a human.

    This closes the human-oversight loop: alerts stay visible until
    a human explicitly marks them as seen.
    """
    try:
        import asyncpg
        from levels.l6_autonomous import init_db_l6, acknowledge_alert
        import os
        conn = await asyncpg.connect(os.getenv("DATABASE_URL", "postgresql://vigil:vigil@db:5432/vigil"))
        try:
            await init_db_l6(conn)
            found = await acknowledge_alert(conn, alert_id, req.acknowledged_by)
            if not found:
                raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found or already acknowledged")
            return {"acknowledged": True, "alert_id": alert_id, "by": req.acknowledged_by}
        finally:
            await conn.close()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/l6/monitor/start", tags=["levels"])
async def start_monitor_l6():
    """
    Start the autonomous monitoring background loop.

    The loop runs inside the FastAPI process as an asyncio.Task.
    It scans the watchlist on the configured interval (VIGIL_SCAN_INTERVAL env var).
    Returns immediately — the loop continues running in the background.
    """
    try:
        from levels.l6_autonomous import start_monitor, SCAN_INTERVAL_SECONDS
        import os
        started = await start_monitor(os.getenv("DATABASE_URL", "postgresql://vigil:vigil@db:5432/vigil"))
        if not started:
            return {"status": "already_running", "scan_interval_seconds": SCAN_INTERVAL_SECONDS}
        return {
            "status":                "started",
            "scan_interval_seconds": SCAN_INTERVAL_SECONDS,
            "message":               "Autonomous monitor is now running. Use GET /l6/monitor/status to check.",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/l6/monitor/stop", tags=["levels"])
async def stop_monitor_l6():
    """
    Kill switch: immediately stop all autonomous monitoring activity.

    The background task is cancelled within seconds. Any in-progress scan
    is interrupted. Safe to call multiple times.
    """
    try:
        from levels.l6_autonomous import stop_monitor
        stopped = await stop_monitor()
        return {
            "status":  "stopped" if stopped else "was_not_running",
            "message": "Autonomous monitor halted." if stopped else "Monitor was not running.",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/l6/monitor/status", tags=["levels"])
async def monitor_status_l6():
    """
    Check whether the autonomous monitor is running and when it last scanned.
    """
    try:
        from levels.l6_autonomous import is_running, SCAN_INTERVAL_SECONDS
        import asyncpg, os
        from levels.l6_autonomous import init_db_l6, get_watchlist, get_alerts
        conn = await asyncpg.connect(os.getenv("DATABASE_URL", "postgresql://vigil:vigil@db:5432/vigil"))
        try:
            await init_db_l6(conn)
            watchlist           = await get_watchlist(conn)
            unacked_alerts      = await get_alerts(conn, unacknowledged_only=True)
            last_scanned_times  = [r["last_scanned"] for r in watchlist if r["last_scanned"]]
            last_scan           = max(last_scanned_times).isoformat() if last_scanned_times else None
        finally:
            await conn.close()

        return {
            "running":                    is_running(),
            "scan_interval_seconds":      SCAN_INTERVAL_SECONDS,
            "watchlist_size":             len(watchlist),
            "unacknowledged_alert_count": len(unacked_alerts),
            "last_scan":                  last_scan,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── ARCHITECTURE 1: ReAct ────────────────────────────────────────────────────
# Concept: explicit Thought → Action → Observe loop with full reasoning trace

class A1Response(BaseModel):
    cve_id:          str
    architecture:    str
    elapsed_ms:      int
    report:          dict
    reasoning_trace: list
    token_usage:     TokenUsage


@app.post("/a1/analyse", response_model=A1Response, tags=["architectures"])
async def analyse_a1(req: CVERequest):
    """
    Architecture 1 — ReAct (Reasoning + Acting).

    The agent writes an explicit Thought before every tool call, producing
    a full Thought → Action → Observation trace alongside the final report.
    Three tools: NVD, EPSS, and CISA Known Exploited Vulnerabilities (KEV).
    Teaches: explicit reasoning, auditability, thought traces vs hidden reasoning.
    """
    try:
        from architectures.a1_react import analyse_cve as react_analyse, get_usage as a1_get_usage
        start = time.perf_counter()

        report, trace = await react_analyse(req.cve_id)

        elapsed_ms = int((time.perf_counter() - start) * 1000)
        return {
            "cve_id":          req.cve_id,
            "architecture":    "ReAct — Thought → Action → Observe",
            "elapsed_ms":      elapsed_ms,
            "report":          report.model_dump(),
            "reasoning_trace": trace,
            "token_usage":     a1_get_usage(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── ARCHITECTURE 2: Plan-and-Execute ─────────────────────────────────────────
# Concept: upfront plan → independent execution of each step

class A2Response(BaseModel):
    cve_id:        str
    architecture:  str
    elapsed_ms:    int
    plan:          dict
    execution_log: list
    report:        dict
    token_usage:   TokenUsage


@app.post("/a2/analyse", response_model=A2Response, tags=["architectures"])
async def analyse_a2(req: CVERequest):
    """
    Architecture 2 — Plan-and-Execute.

    The planner produces a complete investigation plan (one LLM call), then
    the executor runs each step independently. Planning and execution are
    strictly separated — inspect the plan before anything runs.
    Teaches: planning vs acting, step decomposition, human oversight points.
    """
    try:
        from architectures.a2_plan_execute import analyse_cve as pe_analyse, get_usage as a2_get_usage
        start = time.perf_counter()

        plan, report, execution_log = await pe_analyse(req.cve_id)

        elapsed_ms = int((time.perf_counter() - start) * 1000)
        return {
            "cve_id":        req.cve_id,
            "architecture":  "Plan-and-Execute — Plan first, act second",
            "elapsed_ms":    elapsed_ms,
            "plan":          plan.model_dump(),
            "execution_log": execution_log,
            "report":        report.model_dump(),
            "token_usage":   a2_get_usage(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── ARCHITECTURE 3: Reflection / Self-Critique ───────────────────────────────
# Concept: draft → adversarial critique → improved revision

class A3Response(BaseModel):
    cve_id:        str
    architecture:  str
    elapsed_ms:    int
    draft:         dict
    critique:      dict
    report:        dict
    token_usage:   TokenUsage


@app.post("/a3/analyse", response_model=A3Response, tags=["architectures"])
async def analyse_a3(req: CVERequest):
    """
    Architecture 3 — Reflection / Self-Critique.

    The agent produces a draft assessment, then critiques its own work
    (adversarial self-review), then revises to produce the final report.
    All three stages are returned so you can see the improvement.
    Teaches: self-critique, quality loops, draft vs final comparison.
    """
    try:
        from architectures.a3_reflection import analyse_cve as reflect_analyse, get_usage as a3_get_usage
        start = time.perf_counter()

        draft, critique, report = await reflect_analyse(req.cve_id)

        elapsed_ms = int((time.perf_counter() - start) * 1000)
        return {
            "cve_id":       req.cve_id,
            "architecture": "Reflection — Draft → Critique → Revise",
            "elapsed_ms":   elapsed_ms,
            "draft":        draft.model_dump(),
            "critique":     critique.model_dump(),
            "report":       report.model_dump(),
            "token_usage":  a3_get_usage(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── ARCHITECTURE 4: Multi-Agent ─────────────────────────────────────────────
# Concept: orchestrator dispatches parallel specialist agents, then synthesises

class A4Response(BaseModel):
    cve_id:         str
    architecture:   str
    elapsed_ms:     int
    agent_reports:  dict
    tool_log:       list
    report:         dict
    token_usage:    TokenUsage


@app.post("/a4/analyse", response_model=A4Response, tags=["architectures"])
async def analyse_a4(req: CVERequest):
    """
    Architecture 4 — Multi-Agent (Orchestrator + Specialists).

    Three specialist agents run in parallel: Threat Intel, Impact Assessment,
    and Patch & Remediation. Each has its own tools and system prompt.
    An orchestrator synthesises all three reports into a final verdict.
    Teaches: fan-out/fan-in, agent specialisation, orchestration pattern.
    """
    try:
        from architectures.a4_multi_agent import analyse_cve as multi_analyse, get_usage as a4_get_usage
        start = time.perf_counter()

        threat, impact, remediation, report, tool_log = await multi_analyse(req.cve_id)

        elapsed_ms = int((time.perf_counter() - start) * 1000)
        return {
            "cve_id":        req.cve_id,
            "architecture":  "Multi-Agent — Orchestrator + 3 Specialist Agents",
            "elapsed_ms":    elapsed_ms,
            "agent_reports": {
                "threat_intel":      threat.model_dump(),
                "impact_assessment": impact.model_dump(),
                "patch_remediation": remediation.model_dump(),
            },
            "tool_log":      tool_log,
            "report":        report.model_dump(),
            "token_usage":   a4_get_usage(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
