"""
vigil/routers/levels.py — Level endpoints L0-L6 and L4b (multimodal).
"""

from __future__ import annotations

import os
import time
import uuid
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from vigil import hardening
from vigil.models import DiscoveredTool, RecalledMemory
from vigil.schemas import (
    AcknowledgeRequest,
    CVERequest,
    FeedbackRequest,
    L0Response,
    L1Response,
    L2Response,
    L3Response,
    L4bImageRequest,
    L4bPdfRequest,
    L4bResponse,
    L4Response,
    L5Response,
    WatchlistRequest,
)

router = APIRouter()


# ─── LEVEL 0 ──────────────────────────────────────────────────────────────────
# Concept: single LLM call, free-form text response

@router.post("/l0/analyse", response_model=L0Response, tags=["levels"])
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
        key = hardening._cache_key("l0.analyse", req.model_dump())
        cached = hardening._CACHE.get(key)
        if cached is not None:
            return {
                "cve_id":      req.cve_id,
                "level":       0,
                "concept":     "single LLM call",
                "elapsed_ms":  0,
                "explanation": cached["explanation"],
                "cache":       {"from_cache": True, "key": key, "ttl_seconds": hardening._CACHE.ttl(key)},
                "token_usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "estimated_cost_usd": 0.0},
                "trace_id": str(uuid.uuid4()),
            }

        start = time.perf_counter()
        explanation = explain_cve(req.cve_id)
        elapsed_ms  = int((time.perf_counter() - start) * 1000)
        payload = {
            "cve_id":      req.cve_id,
            "level":       0,
            "concept":     "single LLM call",
            "elapsed_ms":  elapsed_ms,
            "explanation": explanation,
            "cache":       {"from_cache": False, "key": key, "ttl_seconds": hardening._CACHE_TTL},
            "token_usage": get_usage(),
            "trace_id": str(uuid.uuid4()),
        }
        hardening._CACHE.set(key, {"explanation": explanation}, ttl_seconds=hardening._CACHE_TTL)
        return payload
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── LEVEL 1 ──────────────────────────────────────────────────────────────────
# Concept: prompt chaining + structured output (Pydantic)

@router.post("/l1/analyse", response_model=L1Response, tags=["levels"])
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
            "trace_id": str(uuid.uuid4()),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/l1/stream", tags=["levels"])
async def stream_l1(cve_id: str = "CVE-2021-44228"):
    """E4 demo endpoint: stream a concise CVE summary token-by-token."""
    try:
        from openai import AsyncOpenAI
        from vigil.inference import astream

        client = AsyncOpenAI(timeout=60.0)

        async def _gen():
            async for token in astream(
                client=client,
                task="default",
                messages=[
                    {"role": "system", "content": "You are a concise CVE explainer."},
                    {
                        "role": "user",
                        "content": (
                            f"Summarize {cve_id} in 5 bullet points: what it is, who is affected, "
                            "exploitability, urgency, and immediate action."
                        ),
                    },
                ],
                temperature=0.1,
                max_tokens=512,
            ):
                yield token

        return StreamingResponse(_gen(), media_type="text/plain")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── LEVEL 2 ──────────────────────────────────────────────────────────────────
# Concept: parallel async fan-out + synthesis

@router.post("/l2/analyse", response_model=L2Response, tags=["levels"])
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
            "trace_id": str(uuid.uuid4()),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── LEVEL 3 ──────────────────────────────────────────────────────────────────
# Concept: conditional routing — LLM decides which pipeline to run

@router.post("/l3/analyse", response_model=L3Response, tags=["levels"])
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
            "trace_id": str(uuid.uuid4()),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── LEVEL 4 ──────────────────────────────────────────────────────────────────
# Concept: tool use — agent calls real external APIs (NVD + EPSS)

@router.post("/l4/analyse", response_model=L4Response, tags=["levels"])
async def analyse_l4(req: CVERequest):
    """
    Level 4 — Tool Use (Grounded Analysis).

    The agent calls the NVD API and EPSS API in a tool-calling loop.
    Analysis is grounded in live data, not model training memory.
    Teaches: tool definitions, the ReAct loop, grounding vs hallucination.
    """
    try:
        from levels.l4_tool_use import analyse_cve as analyse_cve_l4, get_usage as l4_get_usage
        key = hardening._cache_key("l4.analyse", req.model_dump())
        cached = hardening._CACHE.get(key)
        if cached is not None:
            return {
                "cve_id":      req.cve_id,
                "level":       4,
                "concept":     "tool use — grounded analysis via live APIs",
                "elapsed_ms":  0,
                "tool_calls":  cached["tool_calls"],
                "analysis":    cached["analysis"],
                "cache":       {"from_cache": True, "key": key, "ttl_seconds": hardening._CACHE.ttl(key)},
                "token_usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "estimated_cost_usd": 0.0},
                "trace_id":    str(uuid.uuid4()),
            }

        start = time.perf_counter()

        analysis, tool_log = await analyse_cve_l4(req.cve_id)

        elapsed_ms = int((time.perf_counter() - start) * 1000)
        payload = {
            "cve_id":      req.cve_id,
            "level":       4,
            "concept":     "tool use — grounded analysis via live APIs",
            "elapsed_ms":  elapsed_ms,
            "tool_calls":  tool_log,
            "analysis":    analysis.model_dump(),
            "cache":       {"from_cache": False, "key": key, "ttl_seconds": hardening._CACHE_TTL},
            "token_usage": l4_get_usage(),
            "trace_id":    str(uuid.uuid4()),
        }
        hardening._CACHE.set(key, {"tool_calls": tool_log, "analysis": analysis.model_dump()}, ttl_seconds=hardening._CACHE_TTL)
        return payload
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/l4/tools", response_model=list[DiscoveredTool], tags=["levels"])
def tools_l4(source: str = Query(default="inline", pattern="^(inline|mcp)$")):
    """F8: discover available L4 tools from inline definitions or MCP."""
    try:
        from levels.l4_tool_use import discover_tools

        rows = discover_tools(source=source)
        return [DiscoveredTool.model_validate(r) for r in rows]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── LEVEL 4b — MULTIMODAL (F2) ──────────────────────────────────────────────
# Concept: vision + document parsing → structured, grounded extraction


@router.post("/l4b/image", response_model=L4bResponse, tags=["levels"])
async def extract_image_l4b(req: L4bImageRequest):
    """
    Level 4b — Multimodal (Vision).

    Sends an advisory image (URL or base64 data URI) to a vision-capable model
    and extracts a structured `AdvisoryExtract`. Teaches multimodal prompt
    construction (image_url message parts) and visual grounding.
    """
    try:
        from levels.l4b_multimodal import (
            extract_from_image,
            get_usage as l4b_get_usage,
            _reset_usage,
        )
        _reset_usage()
        start = time.perf_counter()

        extract = await extract_from_image(req.image_url)

        return {
            "source_type": "image",
            "concept":     "multimodal vision — structured extraction from an image",
            "elapsed_ms":  int((time.perf_counter() - start) * 1000),
            "extract":     extract.model_dump(),
            "token_usage": l4b_get_usage(),
            "trace_id":    str(uuid.uuid4()),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/l4b/pdf", response_model=L4bResponse, tags=["levels"])
async def extract_pdf_l4b(req: L4bPdfRequest):
    """
    Level 4b — Multimodal (Document parsing).

    Decodes a base64 PDF bulletin, extracts its text, then produces a structured
    `AdvisoryExtract` grounded in the extracted text.
    """
    import base64 as _b64
    import tempfile

    try:
        from levels.l4b_multimodal import (
            extract_from_pdf,
            get_usage as l4b_get_usage,
            _reset_usage,
        )
        _reset_usage()
        start = time.perf_counter()

        try:
            raw = _b64.b64decode(req.content_base64, validate=True)
        except Exception:
            raise HTTPException(status_code=400, detail="content_base64 is not valid base64")

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(raw)
            tmp_path = tmp.name
        try:
            extract = await extract_from_pdf(tmp_path)
        finally:
            try:
                os.remove(tmp_path)
            except OSError:
                pass

        return {
            "source_type": "pdf",
            "concept":     "document parsing — structured extraction from a PDF",
            "elapsed_ms":  int((time.perf_counter() - start) * 1000),
            "extract":     extract.model_dump(),
            "token_usage": l4b_get_usage(),
            "trace_id":    str(uuid.uuid4()),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/l5/analyse", response_model=L5Response, tags=["levels"])
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

        analysis, tool_log, history, context_budget = await analyse_cve_l5(req.cve_id)

        elapsed_ms = int((time.perf_counter() - start) * 1000)
        return {
            "cve_id":              req.cve_id,
            "level":               5,
            "concept":             "memory + feedback loops",
            "elapsed_ms":          elapsed_ms,
            "analysis":            analysis.model_dump(),
            "tool_calls":          tool_log,
            "prior_history_count": len(history),
            "context_budget":      context_budget.model_dump(),
            "token_usage":         l5_get_usage(),
            "trace_id": str(uuid.uuid4()),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/l5/feedback", tags=["levels"])
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


@router.get("/l5/history/{cve_id}", tags=["levels"])
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


@router.get("/l5/similar/{cve_id}", response_model=RecalledMemory, tags=["levels"])
async def similar_l5(cve_id: str, k: int = 5, threshold: float = 0.55):
    """E1 extension: semantic recall over prior analyses for related incidents."""
    try:
        from levels.l5_memory import get_similar_cves

        return await get_similar_cves(cve_id, k=k, threshold=threshold)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/l6/watchlist", tags=["levels"])
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


@router.delete("/l6/watchlist/{cve_id}", tags=["levels"])
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


@router.get("/l6/watchlist", tags=["levels"])
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


@router.post("/l6/scan", tags=["levels"])
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


@router.get("/l6/alerts", tags=["levels"])
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


@router.post("/l6/alerts/{alert_id}/acknowledge", tags=["levels"])
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


@router.post("/l6/monitor/start", tags=["levels"])
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


@router.post("/l6/monitor/stop", tags=["levels"])
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


@router.get("/l6/monitor/status", tags=["levels"])
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
