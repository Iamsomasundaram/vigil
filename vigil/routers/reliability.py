"""
vigil/routers/reliability.py — Reliability endpoints: R1-R5 plus drift, governance, supply chain and release checks.
"""

from __future__ import annotations

import time
import uuid
from fastapi import APIRouter, HTTPException
from vigil.models import (
    ActionDecision,
    BudgetStatus,
    CostReport,
    DriftReport,
    PromotionDecision,
    ReleaseDecision,
    Scorecard,
    SupplyChainReport,
    Trace,
)
from vigil.schemas import (
    ActionCheckRequest,
    CVERequest,
    DriftReportRequest,
    DriftSampleRequest,
    PromotionRequest,
    R1Response,
    R1ScanResponse,
    R2EvaluateRequest,
    R3RunRequest,
    R4Request,
    R4Response,
    R5BudgetRequest,
    ReleaseEvalRequest,
    TextScanRequest,
)

router = APIRouter()


@router.post("/reliability/drift/sample", tags=["reliability"])
def drift_sample(req: DriftSampleRequest):
    """F17: record one online-eval sample into the rolling window."""
    try:
        from reliability.r6_online_eval_drift import record_sample

        record_sample(quality=req.quality, latency_ms=req.latency_ms, cost_usd=req.cost_usd)
        return {"recorded": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reliability/drift/report", response_model=DriftReport, tags=["reliability"])
def drift_report_endpoint(req: DriftReportRequest):
    """F17: compute drift signals and SLO breaches over the rolling window."""
    try:
        from reliability.r6_online_eval_drift import drift_report

        out = drift_report(baseline_quality=req.baseline_quality, slo=req.slo)
        return DriftReport.model_validate(out)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reliability/action/check", response_model=ActionDecision, tags=["reliability"])
def action_check_endpoint(req: ActionCheckRequest):
    """F18: evaluate an agent action against least-privilege permission policy."""
    try:
        from reliability.r7_action_governance import check_action

        out = check_action(
            role=req.role,
            tool=req.tool,
            requested_sandbox=req.requested_sandbox,
            approved=req.approved,
        )
        return ActionDecision.model_validate(out)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/reliability/supply-chain/verify", response_model=SupplyChainReport, tags=["reliability"])
def supply_chain_verify(manifest_path: str = "data/manifests/ai_artifacts.json"):
    """F19: verify AI artifact integrity against the tracked manifest."""
    try:
        from reliability.r8_supply_chain import verify_artifacts

        return SupplyChainReport.model_validate(verify_artifacts(manifest_path))
    except FileNotFoundError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reliability/supply-chain/promote", response_model=PromotionDecision, tags=["reliability"])
def supply_chain_promote(req: PromotionRequest):
    """F19: gate promotion on artifact integrity plus eval status."""
    try:
        from reliability.r8_supply_chain import can_promote

        out = can_promote(path=req.manifest_path, eval_passed=req.eval_passed)
        return PromotionDecision.model_validate(out)
    except FileNotFoundError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reliability/release/evaluate", response_model=ReleaseDecision, tags=["reliability"])
def release_evaluate(req: ReleaseEvalRequest):
    """F20: evaluate a staged rollout (canary) and decide promote/hold/rollback."""
    try:
        from reliability.r9_release_safety import evaluate_release

        out = evaluate_release(
            control_scores=req.control_scores,
            treatment_scores=req.treatment_scores,
            canary_percent=req.canary_percent,
            min_delta=req.min_delta,
        )
        return ReleaseDecision.model_validate(out)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── RELIABILITY R1 ──────────────────────────────────────────────────────────
# Concept: layered guardrails against prompt injection and unsafe downgrades


@router.post("/r1/scan", response_model=R1ScanResponse, tags=["reliability"])
def scan_r1(req: TextScanRequest):
    """
    R1 helper endpoint — scan arbitrary text for prompt-injection indicators.
    """
    try:
        from reliability.r1_guardrails import scan_for_injection

        scan = scan_for_injection(req.text)
        return {"scan": scan}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/r1/analyse", response_model=R1Response, tags=["reliability"])
async def analyse_r1(req: CVERequest):
    """
    Reliability R1 — Guarded CVE analysis.

    Applies input scanning, data isolation, output validation, tool allow-listing,
    and policy/approval gates before returning the final verdict.
    """
    try:
        from reliability.r1_guardrails import analyse_cve as analyse_cve_r1, get_usage as r1_get_usage

        start = time.perf_counter()
        verdict, tool_log = await analyse_cve_r1(req.cve_id)
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        return {
            "cve_id": req.cve_id,
            "level": "R1",
            "concept": "guardrails + prompt-injection defense",
            "elapsed_ms": elapsed_ms,
            "verdict": verdict,
            "tool_calls": tool_log,
            "token_usage": r1_get_usage(),
            "trace_id": str(uuid.uuid4()),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/r2/evaluate", response_model=Scorecard, tags=["reliability"])
async def evaluate_r2(req: R2EvaluateRequest):
    """
    Reliability R2 — evaluation harness and regression gate.

    Runs deterministic checks, judge scoring, and adversarial checks against a
    target module (l1-l4) using a golden dataset.
    """
    try:
        from reliability.r2_evaluation import evaluate

        scorecard = await evaluate(
            target=req.target,
            dataset_path=req.dataset_path,
            rubric_path=req.rubric_path,
            baseline_path=req.baseline_path,
            regression_threshold=req.regression_threshold,
            update_baseline=req.update_baseline,
        )
        return scorecard
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/r3/trace/run", tags=["reliability"])
async def run_r3_trace(req: R3RunRequest):
    """
    Reliability R3 — run a traced L4 analysis and return trace_id.
    """
    try:
        from reliability.r3_observability import run_traced_l4

        payload, _trace = await run_traced_l4(req.cve_id, export_path=req.export_path)
        return payload
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/r3/trace/{trace_id}", response_model=Trace, tags=["reliability"])
def get_r3_trace(trace_id: str, jsonl_path: str | None = None):
    """
    Reliability R3 — fetch a trace by correlation id.
    """
    try:
        from reliability.r3_observability import get_trace

        trace = get_trace(trace_id, jsonl_path=jsonl_path)
        if trace is None:
            raise HTTPException(status_code=404, detail=f"Trace not found: {trace_id}")
        return trace
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/r4/health", tags=["reliability"])
def health_r4():
    """
    Reliability R4 — current circuit-breaker state by source.
    """
    try:
        from reliability.r4_resilience import get_circuit_states

        return {"circuits": get_circuit_states()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/r4/analyse", response_model=R4Response, tags=["reliability"])
async def analyse_r4(req: R4Request):
    """
    Reliability R4 — resilient analysis with timeout/retry/circuit/degradation.
    """
    try:
        from reliability.r4_resilience import analyse_cve as analyse_cve_r4, get_usage as r4_get_usage, parse_chaos

        start = time.perf_counter()
        verdict = await analyse_cve_r4(req.cve_id, chaos=parse_chaos(req.chaos))
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        return {
            "cve_id": req.cve_id,
            "level": "R4",
            "concept": "timeouts + retries + circuit breaker + graceful degradation",
            "elapsed_ms": elapsed_ms,
            "verdict": verdict,
            "token_usage": r4_get_usage(),
            "trace_id": str(uuid.uuid4()),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/r5/budget", response_model=BudgetStatus, tags=["reliability"])
def set_r5_budget(req: R5BudgetRequest):
    """
    Reliability R5 — set request/session budget caps.
    """
    try:
        from reliability.r5_cost_control import set_budget

        return set_budget(
            request_cap_usd=req.request_cap_usd,
            session_cap_usd=req.session_cap_usd,
            warn_ratio=req.warn_ratio,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/r5/report", response_model=CostReport, tags=["reliability"])
def get_r5_report():
    """
    Reliability R5 — aggregated spend/caching report.
    """
    try:
        from reliability.r5_cost_control import get_cost_report

        return get_cost_report()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
