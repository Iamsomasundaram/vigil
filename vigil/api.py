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

import os
import json
import hashlib
import time
import uuid
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
from vigil.cache import CacheBackend
from vigil.models import (
    BudgetStatus,
    CacheInfo,
    Consensus,
    ContextBudgetReport,
    CostReport,
    DiscoveredTool,
    GuardedVerdict,
    HumanDecision,
    InferenceComparison,
    IncidentOpsReport,
    InjectionScan,
    PausedRun,
    ProviderInfo,
    RecalledMemory,
    ResilientVerdict,
    RoutePolicy,
    Scorecard,
    TokenReport,
    Trace,
    PromptComparison,
    RetrievalLabReport,
    RetrievalEvalReport,
    FactualityReport,
    PromptVersion,
    PromptExperimentReport,
    PrivacyReport,
    HybridRetrievalReport,
    DriftReport,
    ActionDecision,
    SupplyChainReport,
    PromotionDecision,
    ReleaseDecision,
    AdaptationRecommendation,
    FinetuneDatasetReport,
    ModelRecommendation,
    ClaudeMappedMessages,
    McpLoopReport,
    ResponsibleAIReport,
    SemanticCacheReport,
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


@app.middleware("http")
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
    cache: CacheInfo | None = None
    token_usage: TokenUsage
    trace_id: str

class L1Response(BaseModel):
    cve_id:      str
    level:       int
    concept:     str
    elapsed_ms:  int
    steps:       dict  # 1_summary, 2_risk, 3_remediation
    token_usage: TokenUsage
    trace_id: str

class L2Response(BaseModel):
    cve_id:        str
    level:         int
    concept:       str
    elapsed_ms:    int
    agent_reports: dict
    verdict:       dict
    token_usage:   TokenUsage
    trace_id: str

class L3Response(BaseModel):
    cve_id:      str
    level:       int
    concept:     str
    elapsed_ms:  int
    routing:     dict
    result:      dict
    token_usage: TokenUsage
    trace_id: str

class L4Response(BaseModel):
    cve_id:      str
    level:       int
    concept:     str
    elapsed_ms:  int
    tool_calls:  list
    analysis:    dict
    cache: CacheInfo | None = None
    token_usage: TokenUsage
    trace_id: str


class TextScanRequest(BaseModel):
    text: str = Field(description="Untrusted text to scan for prompt injection patterns")


class R1ScanResponse(BaseModel):
    scan: InjectionScan


class R1Response(BaseModel):
    cve_id: str
    level: str
    concept: str
    elapsed_ms: int
    verdict: GuardedVerdict
    tool_calls: list
    token_usage: TokenUsage
    trace_id: str


class R2EvaluateRequest(BaseModel):
    target: str = Field(default="l2", description="Target module to evaluate: l1, l2, l3, or l4")
    dataset_path: str = Field(default="data/eval/golden_set.json")
    rubric_path: str = Field(default="data/eval/rubric.md")
    baseline_path: str = Field(default="data/eval/baseline.json")
    regression_threshold: float = Field(default=0.05, ge=0.0)
    update_baseline: bool = False


class R3RunRequest(BaseModel):
    cve_id: str = Field(default="CVE-2021-44228")
    export_path: str | None = None


class R4Request(BaseModel):
    cve_id: str = Field(default="CVE-2021-44228")
    chaos: str = Field(default="", description="Optional chaos config, e.g. epss=timeout,nvd=500")


class R4Response(BaseModel):
    cve_id: str
    level: str
    concept: str
    elapsed_ms: int
    verdict: ResilientVerdict
    token_usage: TokenUsage
    trace_id: str


class R5BudgetRequest(BaseModel):
    request_cap_usd: float = Field(default=0.01, ge=0.0)
    session_cap_usd: float = Field(default=1.0, ge=0.0)
    warn_ratio: float = Field(default=0.8, ge=0.0, le=1.0)


class A2StartRequest(BaseModel):
    cve_id: str = Field(default="CVE-2021-44228")


class A4CollaborateRequest(BaseModel):
    cve_id: str = Field(default="CVE-2021-44228")
    mode: str = Field(default="handoff", description="handoff | debate | blackboard")
    rounds: int = Field(default=2, ge=1, le=5)

class L4bImageRequest(BaseModel):
    image_url: str = Field(
        description="Image URL or base64 data URI of an advisory screenshot",
        examples=["https://example.com/advisory.png"],
    )

class L4bPdfRequest(BaseModel):
    content_base64: str = Field(description="Base64-encoded PDF bytes")
    filename: str = Field(default="advisory.pdf")

class InferenceCompareRequest(BaseModel):
    cve_id: str = Field(default="CVE-2021-44228")
    task: str = Field(default="default")
    providers: list[str] = Field(default_factory=lambda: ["openai"])


class TokenizeRequest(BaseModel):
    text: str = Field(default="CVE-2021-44228 RCE in Log4j")
    model: str | None = None


class PromptCompareRequest(BaseModel):
    cve_id: str = Field(default="CVE-2021-44228")
    advisory_text: str = Field(default="")


class RetrievalLabRequest(BaseModel):
    query: str = Field(default="log4j remote code execution patch")
    chunk_size_words: int = Field(default=80, ge=20, le=500)
    overlap_words: int = Field(default=20, ge=0, le=250)
    top_k: int = Field(default=5, ge=1, le=20)


class RetrievalEvalRequest(BaseModel):
    dataset_path: str = Field(default="data/eval/retrieval_golden.json")
    k: int = Field(default=5, ge=1, le=20)
    chunk_size_a: int = Field(default=80, ge=20, le=500)
    overlap_a: int = Field(default=20, ge=0, le=250)
    chunk_size_b: int = Field(default=120, ge=20, le=500)
    overlap_b: int = Field(default=20, ge=0, le=250)


class FactualityCheckRequest(BaseModel):
    answer_text: str = Field(default="Log4j has remote code execution and patch 2.17.1 is available.")
    evidence_snippets: list[str] = Field(
        default_factory=lambda: [
            "CVE-2021-44228 allows remote code execution in Apache Log4j.",
            "Patch to Log4j 2.17.1 or later is recommended.",
        ]
    )
    support_threshold: float = Field(default=0.45, ge=0.0, le=1.0)


class PromptVersionsRequest(BaseModel):
    path: str = Field(default="data/prompts/f14_prompt_versions.json")


class PromptCompareVersionsRequest(BaseModel):
    version_a: str = Field(default="v1")
    version_b: str = Field(default="v2")
    items: list[str] = Field(default_factory=lambda: ["CVE-2021-44228", "CVE-2023-44487", "CVE-2014-0160"])
    path: str = Field(default="data/prompts/f14_prompt_versions.json")


class PrivacyRedactRequest(BaseModel):
    text: str = Field(default="Contact ops@example.com from 10.20.30.40 token=abc123")
    sample_payload: dict | None = None


class HybridRetrievalRequest(BaseModel):
    query: str = Field(default="log4j remote code execution patch")
    chunk_size_words: int = Field(default=80, ge=20, le=500)
    overlap_words: int = Field(default=20, ge=0, le=250)
    alpha: float = Field(default=0.5, ge=0.0, le=1.0)
    rerank: bool = Field(default=False)
    top_k: int = Field(default=5, ge=1, le=20)


class DriftSampleRequest(BaseModel):
    quality: float = Field(ge=0.0, le=1.0)
    latency_ms: float = Field(ge=0.0)
    cost_usd: float = Field(ge=0.0)


class DriftReportRequest(BaseModel):
    baseline_quality: float = Field(default=0.8, ge=0.0, le=1.0)
    slo: dict[str, float] | None = None


class ActionCheckRequest(BaseModel):
    role: str = Field(default="analyst")
    tool: str = Field(default="apply_patch")
    requested_sandbox: str = Field(default="execute")
    approved: bool = Field(default=False)


class PromotionRequest(BaseModel):
    manifest_path: str = Field(default="data/manifests/ai_artifacts.json")
    eval_passed: bool = Field(default=True)


class ReleaseEvalRequest(BaseModel):
    control_scores: list[float] = Field(default_factory=lambda: [0.80, 0.82, 0.79])
    treatment_scores: list[float] = Field(default_factory=lambda: [0.81, 0.83, 0.80])
    canary_percent: int = Field(default=10, ge=0, le=100)
    min_delta: float = Field(default=-0.02)


class AdaptationRequest(BaseModel):
    task_stability: str = Field(default="stable")
    data_volume: int = Field(default=1500, ge=0)
    needs_fresh_knowledge: bool = Field(default=False)
    strict_format: bool = Field(default=True)
    latency_sensitive: bool = Field(default=False)
    domain_shift: str = Field(default="low")


class FinetuneDatasetRequest(BaseModel):
    records: list[dict] = Field(default_factory=list)


class ModelSelectRequest(BaseModel):
    task_complexity: str = Field(default="medium")
    latency_sensitive: bool = Field(default=False)
    cost_sensitive: bool = Field(default=False)
    high_volume: bool = Field(default=False)
    high_stakes: bool = Field(default=False)


class ClaudeMapRequest(BaseModel):
    messages: list[dict] = Field(
        default_factory=lambda: [
            {"role": "system", "content": "You are a CVE analyst."},
            {"role": "user", "content": "Summarize CVE-2021-44228."},
        ]
    )


class McpLoopRequest(BaseModel):
    cve_id: str = Field(default="CVE-2021-44228")


class ResponsibleAIRequest(BaseModel):
    texts: list[str] = Field(default_factory=lambda: ["This tool is great", "You stupid loser"])
    outcomes: list[dict] = Field(
        default_factory=lambda: [
            {"group": "group_a", "positive": True},
            {"group": "group_b", "positive": False},
        ]
    )


class SemanticCacheRequest(BaseModel):
    pairs: list[dict] = Field(
        default_factory=lambda: [
            {"query": "What is CVE-2021-44228?", "response": "Log4Shell RCE"},
            {"query": "Tell me about CVE-2021-44228", "response": "Log4Shell RCE"},
        ]
    )
    threshold: float = Field(default=0.8, ge=0.0, le=1.0)


class IncidentThemeRequest(BaseModel):
    alert_text: str = Field(default="Payment API error rate surged and customer checkouts are failing")
    service_name: str = Field(default="payments-api")
    customer_impact: bool = Field(default=True)
    signals: list[str] = Field(default_factory=lambda: ["latency", "error rate", "checkout failures"])


class IncidentThemeResponse(BaseModel):
    theme: str
    scenario: str
    elapsed_ms: int
    report: IncidentOpsReport

class L4bResponse(BaseModel):
    source_type: str
    concept:     str
    elapsed_ms:  int
    extract:     dict
    token_usage: TokenUsage
    trace_id:    str

class L5Response(BaseModel):
    cve_id:               str
    level:                int
    concept:              str
    elapsed_ms:           int
    analysis:             dict
    tool_calls:           list
    prior_history_count:  int
    context_budget:       ContextBudgetReport
    token_usage:          TokenUsage
    trace_id: str

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


@app.get("/admin/ratelimit", tags=["system"])
def admin_ratelimit(request: Request):
    """Inspect in-memory rate bucket state (local diagnostics)."""
    if _API_KEYS:
        api_key = request.headers.get("x-api-key")
        if api_key not in _API_KEYS:
            raise HTTPException(status_code=401, detail="Missing or invalid API key")
    return {"rate_per_min": _RATE_PER_MIN, "buckets": _RATE_STATE}


@app.post("/foundations/tokenize", response_model=TokenReport, tags=["foundations"])
def tokenize_foundations(req: TokenizeRequest):
    """F4: tokenize text, report token count vs context limit and projected cost."""
    try:
        from levels.foundations.tokenization import tokenize_report

        model = req.model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        return TokenReport.model_validate(tokenize_report(req.text, model=model))
    except ModuleNotFoundError as e:
        raise HTTPException(status_code=503, detail=f"Tokenizer dependency missing ({e}). Install with: pip install -e .[foundations]")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/foundations/prompt-compare", response_model=PromptComparison, tags=["foundations"])
async def prompt_compare_foundations(req: PromptCompareRequest):
    """F6: compare prompt techniques on the same CVE task."""
    try:
        from levels.foundations.prompting import prompt_compare

        return PromptComparison.model_validate(await prompt_compare(req.cve_id, req.advisory_text))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/foundations/retrieval-lab", response_model=RetrievalLabReport, tags=["foundations"])
def retrieval_lab_foundations(req: RetrievalLabRequest):
    """F11: tune chunking/indexing settings and inspect ranked retrieval hits."""
    try:
        from levels.foundations.retrieval_quality import retrieval_lab

        return RetrievalLabReport.model_validate(
            retrieval_lab(
                query=req.query,
                chunk_size_words=req.chunk_size_words,
                overlap_words=req.overlap_words,
                top_k=req.top_k,
            )
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/foundations/retrieval-eval", response_model=RetrievalEvalReport, tags=["foundations"])
def retrieval_eval_foundations(req: RetrievalEvalRequest):
    """F12: evaluate retrieval quality using Recall@k, MRR, and nDCG."""
    try:
        from levels.foundations.retrieval_quality import evaluate_retrieval_settings

        out = evaluate_retrieval_settings(
            dataset_path=req.dataset_path,
            chunk_size_a=req.chunk_size_a,
            overlap_a=req.overlap_a,
            chunk_size_b=req.chunk_size_b,
            overlap_b=req.overlap_b,
            k=req.k,
        )
        return RetrievalEvalReport.model_validate(out)
    except FileNotFoundError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/foundations/factuality-check", response_model=FactualityReport, tags=["foundations"])
def factuality_check_foundations(req: FactualityCheckRequest):
    """F13: verify answer claims against provided evidence snippets."""
    try:
        from levels.foundations.factuality import factuality_check

        out = factuality_check(
            answer_text=req.answer_text,
            evidence_snippets=req.evidence_snippets,
            support_threshold=req.support_threshold,
        )
        return FactualityReport.model_validate(out)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/foundations/prompt-versions", response_model=list[PromptVersion], tags=["foundations"])
def prompt_versions_foundations(path: str = "data/prompts/f14_prompt_versions.json"):
    """F14: list available prompt versions for replay/experimentation."""
    try:
        from levels.foundations.prompt_lifecycle import list_versions

        return [PromptVersion.model_validate(v) for v in list_versions(path)]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/foundations/prompt-versions/compare", response_model=PromptExperimentReport, tags=["foundations"])
def prompt_versions_compare_foundations(req: PromptCompareVersionsRequest):
    """F14: compare prompt versions on fixed items and return a winner."""
    try:
        from levels.foundations.prompt_lifecycle import compare_versions

        out = compare_versions(
            version_a=req.version_a,
            version_b=req.version_b,
            items=req.items,
            path=req.path,
        )
        return PromptExperimentReport.model_validate(out)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/foundations/privacy/redact", response_model=PrivacyReport, tags=["foundations"])
def privacy_redact_foundations(req: PrivacyRedactRequest):
    """F15: redact sensitive patterns and produce a safe log snapshot."""
    try:
        from levels.foundations.privacy import privacy_report

        out = privacy_report(req.text, sample_payload=req.sample_payload)
        return PrivacyReport.model_validate(out)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/foundations/hybrid-retrieval", response_model=HybridRetrievalReport, tags=["foundations"])
def hybrid_retrieval_foundations(req: HybridRetrievalRequest):
    """F16: compare lexical, vector, and hybrid retrieval with optional reranking."""
    try:
        from levels.foundations.retrieval_quality import hybrid_lab

        out = hybrid_lab(
            query=req.query,
            chunk_size_words=req.chunk_size_words,
            overlap_words=req.overlap_words,
            alpha=req.alpha,
            rerank=req.rerank,
            top_k=req.top_k,
        )
        return HybridRetrievalReport.model_validate(out)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/reliability/drift/sample", tags=["reliability"])
def drift_sample(req: DriftSampleRequest):
    """F17: record one online-eval sample into the rolling window."""
    try:
        from reliability.r6_online_eval_drift import record_sample

        record_sample(quality=req.quality, latency_ms=req.latency_ms, cost_usd=req.cost_usd)
        return {"recorded": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/reliability/drift/report", response_model=DriftReport, tags=["reliability"])
def drift_report_endpoint(req: DriftReportRequest):
    """F17: compute drift signals and SLO breaches over the rolling window."""
    try:
        from reliability.r6_online_eval_drift import drift_report

        out = drift_report(baseline_quality=req.baseline_quality, slo=req.slo)
        return DriftReport.model_validate(out)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/reliability/action/check", response_model=ActionDecision, tags=["reliability"])
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


@app.get("/reliability/supply-chain/verify", response_model=SupplyChainReport, tags=["reliability"])
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


@app.post("/reliability/supply-chain/promote", response_model=PromotionDecision, tags=["reliability"])
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


@app.post("/reliability/release/evaluate", response_model=ReleaseDecision, tags=["reliability"])
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


@app.post("/foundations/adaptation/recommend", response_model=AdaptationRecommendation, tags=["foundations"])
def adaptation_recommend(req: AdaptationRequest):
    """F21: recommend prompt/few-shot/RAG/fine-tune approach from task traits."""
    try:
        from levels.foundations.finetuning import recommend_approach

        out = recommend_approach(
            task_stability=req.task_stability,
            data_volume=req.data_volume,
            needs_fresh_knowledge=req.needs_fresh_knowledge,
            strict_format=req.strict_format,
            latency_sensitive=req.latency_sensitive,
            domain_shift=req.domain_shift,
        )
        return AdaptationRecommendation.model_validate(out)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/foundations/finetune/validate", response_model=FinetuneDatasetReport, tags=["foundations"])
def finetune_validate(req: FinetuneDatasetRequest):
    """F21: validate a chat-style fine-tuning dataset for common quality issues."""
    try:
        from levels.foundations.finetuning import validate_finetune_dataset

        return FinetuneDatasetReport.model_validate(validate_finetune_dataset(req.records))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/foundations/model-select", response_model=ModelRecommendation, tags=["foundations"])
def model_select_foundations(req: ModelSelectRequest):
    """F22: recommend a Claude model tier (Haiku/Sonnet/Opus) from constraints."""
    try:
        from levels.foundations.model_selection import recommend_model

        out = recommend_model(
            task_complexity=req.task_complexity,
            latency_sensitive=req.latency_sensitive,
            cost_sensitive=req.cost_sensitive,
            high_volume=req.high_volume,
            high_stakes=req.high_stakes,
        )
        return ModelRecommendation.model_validate(out)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/claude/map-messages", response_model=ClaudeMappedMessages, tags=["claude"])
def claude_map_messages(req: ClaudeMapRequest):
    """Claude bridge: map OpenAI-style messages to Claude Messages API shape."""
    try:
        from vigil.claude_provider import map_messages_to_claude

        return ClaudeMappedMessages.model_validate(map_messages_to_claude(req.messages))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/mcp/tool-loop", response_model=McpLoopReport, tags=["claude"])
async def mcp_tool_loop(req: McpLoopRequest):
    """MCP client path: run a deterministic tool loop over the MCP server tools."""
    try:
        from vigil_mcp.vigil_client import run_tool_loop

        return McpLoopReport.model_validate(await run_tool_loop(cve_id=req.cve_id))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/foundations/responsible-ai", response_model=ResponsibleAIReport, tags=["foundations"])
def responsible_ai_foundations(req: ResponsibleAIRequest):
    """F23: content moderation + fairness (demographic parity) evaluation."""
    try:
        from levels.foundations.responsible_ai import responsible_ai_report

        out = responsible_ai_report(texts=req.texts, outcomes=req.outcomes)
        return ResponsibleAIReport.model_validate(out)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/foundations/semantic-cache", response_model=SemanticCacheReport, tags=["foundations"])
def semantic_cache_foundations(req: SemanticCacheRequest):
    """F24: replay queries through a similarity-based semantic cache."""
    try:
        from levels.foundations.semantic_cache import simulate

        return SemanticCacheReport.model_validate(simulate(req.pairs, threshold=req.threshold))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/themes/incident/analyse", response_model=IncidentThemeResponse, tags=["themes"])
def analyse_theme_incident(req: IncidentThemeRequest):
    """T1: domain transfer demo from CVE workflows to incident-response operations."""
    try:
        from levels.themes.incident_ops import analyse_incident

        start = time.perf_counter()
        report = analyse_incident(
            alert_text=req.alert_text,
            service_name=req.service_name,
            customer_impact=req.customer_impact,
            signals=req.signals,
        )
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        return {
            "theme": "T1",
            "scenario": "Incident Response Ops",
            "elapsed_ms": elapsed_ms,
            "report": report,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/inference/policy", response_model=list[RoutePolicy], tags=["extensions"])
def inference_policy():
    """Return configured inference routing/fallback policies."""
    try:
        from vigil.inference import get_all_policies

        return get_all_policies()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/inference/providers", response_model=list[ProviderInfo], tags=["extensions"])
def inference_providers():
    """List configured inference providers and their capability flags (F3)."""
    try:
        from vigil.inference import get_providers

        return get_providers()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/inference/compare", response_model=InferenceComparison, tags=["extensions"])
async def inference_compare(req: InferenceCompareRequest):
    """Run the same prompt across providers and compare latency/cost/output (F3)."""
    try:
        from vigil.inference import compare_inference

        messages = [
            {
                "role": "user",
                "content": f"In two sentences, summarise the risk of {req.cve_id}.",
            }
        ]
        return await compare_inference(
            messages=messages,
            task=req.task,
            providers=req.providers,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/frameworks/a1", tags=["architectures"])
async def framework_a1(req: CVERequest):
    """F7: run the A1-style LangGraph port (or fallback when deps are absent)."""
    try:
        from architectures.frameworks.a1_react_langgraph import analyse_cve

        return await analyse_cve(req.cve_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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
        key = _cache_key("l0.analyse", req.model_dump())
        cached = _CACHE.get(key)
        if cached is not None:
            return {
                "cve_id":      req.cve_id,
                "level":       0,
                "concept":     "single LLM call",
                "elapsed_ms":  0,
                "explanation": cached["explanation"],
                "cache":       {"from_cache": True, "key": key, "ttl_seconds": _CACHE.ttl(key)},
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
            "cache":       {"from_cache": False, "key": key, "ttl_seconds": _CACHE_TTL},
            "token_usage": get_usage(),
            "trace_id": str(uuid.uuid4()),
        }
        _CACHE.set(key, {"explanation": explanation}, ttl_seconds=_CACHE_TTL)
        return payload
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
            "trace_id": str(uuid.uuid4()),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/l1/stream", tags=["levels"])
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
            "trace_id": str(uuid.uuid4()),
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
            "trace_id": str(uuid.uuid4()),
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
        key = _cache_key("l4.analyse", req.model_dump())
        cached = _CACHE.get(key)
        if cached is not None:
            return {
                "cve_id":      req.cve_id,
                "level":       4,
                "concept":     "tool use — grounded analysis via live APIs",
                "elapsed_ms":  0,
                "tool_calls":  cached["tool_calls"],
                "analysis":    cached["analysis"],
                "cache":       {"from_cache": True, "key": key, "ttl_seconds": _CACHE.ttl(key)},
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
            "cache":       {"from_cache": False, "key": key, "ttl_seconds": _CACHE_TTL},
            "token_usage": l4_get_usage(),
            "trace_id":    str(uuid.uuid4()),
        }
        _CACHE.set(key, {"tool_calls": tool_log, "analysis": analysis.model_dump()}, ttl_seconds=_CACHE_TTL)
        return payload
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/l4/tools", response_model=list[DiscoveredTool], tags=["levels"])
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


@app.post("/l4b/image", response_model=L4bResponse, tags=["levels"])
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


@app.post("/l4b/pdf", response_model=L4bResponse, tags=["levels"])
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


# ─── RELIABILITY R1 ──────────────────────────────────────────────────────────
# Concept: layered guardrails against prompt injection and unsafe downgrades


@app.post("/r1/scan", response_model=R1ScanResponse, tags=["reliability"])
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


@app.post("/r1/analyse", response_model=R1Response, tags=["reliability"])
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


@app.post("/r2/evaluate", response_model=Scorecard, tags=["reliability"])
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


@app.post("/r3/trace/run", tags=["reliability"])
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


@app.get("/r3/trace/{trace_id}", response_model=Trace, tags=["reliability"])
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


@app.get("/r4/health", tags=["reliability"])
def health_r4():
    """
    Reliability R4 — current circuit-breaker state by source.
    """
    try:
        from reliability.r4_resilience import get_circuit_states

        return {"circuits": get_circuit_states()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/r4/analyse", response_model=R4Response, tags=["reliability"])
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


@app.post("/r5/budget", response_model=BudgetStatus, tags=["reliability"])
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


@app.get("/r5/report", response_model=CostReport, tags=["reliability"])
def get_r5_report():
    """
    Reliability R5 — aggregated spend/caching report.
    """
    try:
        from reliability.r5_cost_control import get_cost_report

        return get_cost_report()
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


@app.get("/l5/similar/{cve_id}", response_model=RecalledMemory, tags=["levels"])
async def similar_l5(cve_id: str, k: int = 5, threshold: float = 0.55):
    """E1 extension: semantic recall over prior analyses for related incidents."""
    try:
        from levels.l5_memory import get_similar_cves

        return await get_similar_cves(cve_id, k=k, threshold=threshold)
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


@app.post("/a2/start", response_model=PausedRun, tags=["architectures"])
async def start_a2(req: A2StartRequest):
    """E2 extension: create a paused Plan-and-Execute run awaiting human approval."""
    try:
        from architectures.a2_plan_execute import start_gated_run

        return await start_gated_run(req.cve_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/a2/runs/{run_id}", tags=["architectures"])
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


@app.post("/a2/runs/{run_id}/decision", response_model=PausedRun, tags=["architectures"])
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


@app.post("/a4/collaborate", response_model=Consensus, tags=["architectures"])
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
