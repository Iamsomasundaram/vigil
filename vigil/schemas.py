"""
vigil/schemas.py — Request and response models for the HTTP API.

Shared domain models live in ``vigil/models.py``; this file holds the shapes that
are specific to the API layer. Routers import from here.
"""

from __future__ import annotations

from pydantic import BaseModel, Field
from vigil.models import (
    CacheInfo,
    ContextBudgetReport,
    GuardedVerdict,
    IncidentOpsReport,
    InjectionScan,
    ResilientVerdict,
)
from vigil.pricing import PRICING_NOTE


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
    estimated_cost_usd: float = Field(description="Estimated cost in USD. " + PRICING_NOTE)


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


# ─── LEVEL 6 ──────────────────────────────────────────────────────────────────
# Concept: fully autonomous monitoring — the agent acts without being asked.
#
# Seven endpoints covering the full autonomous lifecycle:
#   Watchlist management → manual scan → alerts → monitor start/stop/status

class WatchlistRequest(BaseModel):
    cve_id: str = Field(examples=["CVE-2021-44228"])


class AcknowledgeRequest(BaseModel):
    acknowledged_by: str = Field(default="api", examples=["security-team"])


# ─── ARCHITECTURE 1: ReAct ────────────────────────────────────────────────────
# Concept: explicit Thought → Action → Observe loop with full reasoning trace

class A1Response(BaseModel):
    cve_id:          str
    architecture:    str
    elapsed_ms:      int
    report:          dict
    reasoning_trace: list
    token_usage:     TokenUsage


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
