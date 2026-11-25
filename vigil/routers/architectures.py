"""
vigil/routers/architectures.py — Agent architecture endpoints (A1-A4) and the framework bridge.
"""

from __future__ import annotations

import time
from fastapi import APIRouter, HTTPException
from vigil.models import Consensus, HumanDecision, PausedRun
from vigil.schemas import (
    A1Response,
    A2Response,
    A2StartRequest,
    A3Response,
    A4CollaborateRequest,
    A4Response,
    CVERequest,
)

router = APIRouter()


@router.post("/frameworks/a1", tags=["architectures"])
async def framework_a1(req: CVERequest):
    """F7: run the A1-style LangGraph port (or fallback when deps are absent)."""
    try:
        from architectures.frameworks.a1_react_langgraph import analyse_cve

        return await analyse_cve(req.cve_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/a1/analyse", response_model=A1Response, tags=["architectures"])
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


@router.post("/a2/analyse", response_model=A2Response, tags=["architectures"])
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


@router.post("/a2/start", response_model=PausedRun, tags=["architectures"])
async def start_a2(req: A2StartRequest):
    """E2 extension: create a paused Plan-and-Execute run awaiting human approval."""
    try:
        from architectures.a2_plan_execute import start_gated_run

        return await start_gated_run(req.cve_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/a2/runs/{run_id}", tags=["architectures"])
async def get_a2_run(run_id: str):
    """Return current HITL run state and any completed artifacts."""
    try:
        from architectures.a2_plan_execute import get_gated_run_details

        details = get_gated_run_details(run_id)
        if details is None:
            raise HTTPException(status_code=404, detail="Run not found")

        report = details["report"]
        return {
            "run": details["run"],
            "execution_log": details["execution_log"],
            "report": report.model_dump() if hasattr(report, "model_dump") else report,
            "audit": details["audit"],
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/a2/runs/{run_id}/decision", response_model=PausedRun, tags=["architectures"])
async def decide_a2_run(run_id: str, decision: HumanDecision):
    """Submit approve/reject/edit/request_changes for the current open gate."""
    try:
        from architectures.a2_plan_execute import submit_human_decision

        state = await submit_human_decision(decision)
        if state.run_id != run_id:
            raise HTTPException(status_code=400, detail="Decision gate does not belong to run_id")
        return state
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/a3/analyse", response_model=A3Response, tags=["architectures"])
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


@router.post("/a4/analyse", response_model=A4Response, tags=["architectures"])
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


@router.post("/a4/collaborate", response_model=Consensus, tags=["architectures"])
async def collaborate_a4(req: A4CollaborateRequest):
    """E3 extension: run A4 with explicit inter-agent communication mode."""
    try:
        from architectures.a4_multi_agent import collaborate

        mode = req.mode.strip().lower()
        if mode not in {"handoff", "debate", "blackboard"}:
            raise HTTPException(status_code=400, detail="mode must be handoff|debate|blackboard")

        return await collaborate(req.cve_id, mode=mode, rounds=req.rounds)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
