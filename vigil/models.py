"""
vigil/models.py — Shared Pydantic Schemas
==========================================
Pydantic models define the STRUCTURE of data flowing between agents.

Why this matters for AI systems:
  Without structured output, LLMs return free-form text that is hard to
  parse, validate, or pass to the next step reliably. Pydantic forces the
  model to return typed JSON that your code can trust.

How it works:
  You pass a Pydantic model as `response_format` to the OpenAI API.
  The model is constrained to return JSON that matches the schema.
  If it doesn't, the SDK raises a validation error — not a silent bug.

Used by: L2 and above (L0/L1 define their own inline for clarity).
"""

from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class _Base(BaseModel):
    """Strict base model for newer modules that require schema hardening."""

    model_config = ConfigDict(extra="forbid")


# ─── L2: Parallel Agent Output Models ────────────────────────────────────────
# Each of the four specialist agents returns one of these models.
# Having separate models per agent keeps outputs focused and typed.

class ExploitabilityAnalysis(BaseModel):
    """Output of the Exploitability Agent.
    Answers: How easy is this CVE to exploit right now?
    """
    attack_complexity: Literal["Low", "High"]
    privileges_required: Literal["None", "Low", "High"]
    user_interaction_required: bool
    public_exploit_available: bool
    actively_exploited_in_wild: bool
    exploitability_score: float = Field(ge=0.0, le=10.0)
    reasoning: str


class ImpactAnalysis(BaseModel):
    """Output of the Impact Agent.
    Answers: If exploited, what is the damage?
    """
    confidentiality_impact: Literal["None", "Low", "High"]
    integrity_impact: Literal["None", "Low", "High"]
    availability_impact: Literal["None", "Low", "High"]
    blast_radius: Literal["Single Host", "Internal Network", "Whole Organisation"]
    data_types_at_risk: list[str]
    impact_score: float = Field(ge=0.0, le=10.0)
    reasoning: str


class PatchAnalysis(BaseModel):
    """Output of the Patch Agent.
    Answers: Is there a fix, and what does applying it involve?
    """
    patch_available: bool
    patched_version: str | None = None
    workaround_available: bool
    workaround_description: str | None = None
    patch_complexity: Literal["Low", "Medium", "High"]
    estimated_downtime_required: bool
    recommended_action: str


class BusinessImpactAnalysis(BaseModel):
    """Output of the Business Impact Agent.
    Answers: What business processes and compliance obligations are at risk?
    """
    affected_service_types: list[str]
    business_risk_level: Literal["Critical", "High", "Medium", "Low"]
    compliance_frameworks_at_risk: list[str]
    customer_data_at_risk: bool
    estimated_breach_cost_range: str
    reasoning: str


# ─── L2: Aggregated Committee Report ─────────────────────────────────────────
# After all four agents run in parallel, their outputs are merged into this.

class ParallelAssessment(BaseModel):
    """The combined output of all four parallel agents.
    This is what gets passed to the next step (moderator, report, etc.).
    """
    cve_id: str
    exploitability: ExploitabilityAnalysis
    impact: ImpactAnalysis
    patch: PatchAnalysis
    business: BusinessImpactAnalysis
    overall_priority: Literal["Critical", "High", "Medium", "Low"]
    recommended_sla_days: int = Field(ge=0)


# ─── L3+: Routing Models ─────────────────────────────────────────────────────
# Used when the system decides which specialist agents to invoke.

class RoutingDecision(BaseModel):
    """Output of the router — decides which specialist track to activate."""
    cve_type: Literal[
        "network_infrastructure",
        "web_application",
        "os_kernel",
        "cloud_misconfiguration",
        "supply_chain_dependency",
        "unknown",
    ]
    activated_agents: list[str]
    routing_reason: str
    confidence: Literal["Low", "Medium", "High"]


# ─── R1: Guardrails & Prompt-Injection Defense ──────────────────────────────

class InjectionScan(_Base):
    """Heuristic prompt-injection scan result for untrusted text."""

    is_suspicious: bool
    risk_score: float = Field(ge=0.0, le=1.0)
    techniques: list[str]
    matched_spans: list[str]


class GuardedVerdict(_Base):
    """Final guarded decision after input/output policy checks."""

    cve_id: str
    severity: Literal["Critical", "High", "Medium", "Low", "None"]
    recommended_action: str
    requires_human_review: bool
    review_reason: str | None = None
    guardrails_triggered: list[str]
    injection_scan: InjectionScan


# ─── R2: Evaluation & Regression Testing ───────────────────────────────────

class EvalCase(_Base):
    cve_id: str
    expected_severity_band: list[str]
    expected_kev: bool
    action_required: bool
    notes: str | None = None


class MetricResult(_Base):
    name: str
    metric_type: Literal["deterministic", "llm_judge", "adversarial"]
    score: float = Field(ge=0.0, le=1.0)
    passed: bool
    detail: str | None = None


class Scorecard(_Base):
    target: str
    n_cases: int = Field(ge=0)
    metrics: list[MetricResult]
    overall_score: float = Field(ge=0.0, le=1.0)
    estimated_cost_usd: float = Field(ge=0.0)
    regression_vs_baseline: float | None = None
    regression_threshold: float = Field(ge=0.0, default=0.05)
    passed_regression: bool = True
    rubric_version: str = "rubric.md"


# ─── R3: Observability & Tracing ───────────────────────────────────────────

class Span(_Base):
    span_id: str
    parent_id: str | None = None
    name: str
    attributes: dict[str, str] = Field(default_factory=dict)
    start_ms: float
    duration_ms: float = Field(ge=0.0)
    status: Literal["ok", "error"]
    tokens: int | None = None


class Trace(_Base):
    trace_id: str
    root_span_id: str
    spans: list[Span]
    total_duration_ms: float = Field(ge=0.0)
    total_tokens: int = Field(ge=0)
    estimated_cost_usd: float = Field(ge=0.0)


# ─── R4: Resilience in the Agent Loop ──────────────────────────────────────

class SourceStatus(_Base):
    name: str
    available: bool
    attempts: int = Field(ge=0)
    circuit: Literal["closed", "open", "half_open"]


class ResilientVerdict(_Base):
    cve_id: str
    confidence: float = Field(ge=0.0, le=1.0)
    degraded_sources: list[str]
    sources: list[SourceStatus]
    summary: str


# ─── R5: Cost Control & Token Economics ────────────────────────────────────

class CostEntry(_Base):
    feature: str
    cve_id: str | None = None
    model: str
    prompt_tokens: int = Field(ge=0)
    completion_tokens: int = Field(ge=0)
    cost_usd: float = Field(ge=0.0)
    cache_hit: bool


class BudgetStatus(_Base):
    limit_usd: float = Field(ge=0.0)
    spent_usd: float = Field(ge=0.0)
    remaining_usd: float = Field(ge=0.0)
    exceeded: bool


class CostReport(_Base):
    entries: list[CostEntry]
    total_usd: float = Field(ge=0.0)
    by_feature: dict[str, float]
    by_model: dict[str, float]
    cache_savings_usd: float = Field(ge=0.0)


# ─── E1: Semantic Memory (L5 extension) ───────────────────────────────────

class SemanticMatch(_Base):
    cve_id: str
    similarity: float = Field(ge=0.0, le=1.0)
    summary: str
    outcome: str | None = None


class RecalledMemory(_Base):
    query_cve_id: str
    matches: list[SemanticMatch]
    used_in_prompt: bool
    # F1: which embedding backend produced these vectors.
    embedding_mode: str = "local"   # "local" | "openai"
    embedding_dims: int = 32


class ContextBudgetReport(_Base):
    """F5: how the L5 memory context was fit into a fixed token budget."""
    budget_tokens: int = Field(ge=0)
    used_tokens: int = Field(ge=0)
    entries_verbatim: int = Field(ge=0)
    entries_summarized: int = Field(ge=0)
    was_truncated: bool
    was_summarized: bool


# ─── F2: Multimodal (vision + document parsing) ───────────────────────────

class ExtractedField(_Base):
    """One free-form field the model pulled out of an advisory."""
    name: str
    value: str


class AdvisoryExtract(_Base):
    """Structured data extracted from an advisory image or PDF.

    Nullable identity fields because a screenshot/bulletin may not state every
    value. `grounding_quotes` holds the exact source lines/phrases the model
    relied on, so extraction stays traceable rather than hallucinated.
    """
    cve_id:           str | None
    affected_product: str | None
    claimed_severity: str | None
    source_type:      str                  # "image" | "pdf"
    extracted_fields: list[ExtractedField]
    grounding_quotes: list[str]


# ─── E2: Human-in-the-Loop (A2 extension) ─────────────────────────────────

class ApprovalGate(_Base):
    gate_id: str
    run_id: str
    gate_type: Literal["plan", "action", "clarification"]
    payload: str
    risk: Literal["low", "medium", "high"]


class HumanDecision(_Base):
    gate_id: str
    decision: Literal["approve", "reject", "edit", "request_changes"]
    edited_payload: str | None = None
    rationale: str | None = None
    actor: str


class PausedRun(_Base):
    run_id: str
    cve_id: str
    state: Literal["pending_plan_approval", "executing", "pending_action_approval", "done", "aborted"]
    open_gate: ApprovalGate | None = None


# ─── E3: Agent Communication (A4 extension) ───────────────────────────────

class AgentMessage(_Base):
    sender: str
    recipient: str
    round: int
    content: str


class DebateRound(_Base):
    round: int
    claims: dict[str, str]
    rebuttals: dict[str, str]


class Blackboard(_Base):
    facts: list[str]
    claims: list[str]
    open_questions: list[str]


class Consensus(_Base):
    mode: Literal["handoff", "debate", "blackboard"]
    transcript: list[AgentMessage]
    rounds_used: int = Field(ge=1)
    final_verdict: str
    disagreement_noted: bool


# ─── E4: Inference Layer (shared extension) ───────────────────────────────

class RoutePolicy(_Base):
    task: str
    primary: str
    fallbacks: list[str]
    provider: str = "openai"            # openai | ollama | openai_compatible
    base_url: str | None = None
    supports_tools: bool = True
    supports_json_schema: bool = True


class InferenceResult(_Base):
    model_used: str
    fell_back: bool
    attempts: int = Field(ge=1)
    prompt_tokens: int = Field(ge=0)
    completion_tokens: int = Field(ge=0)
    cost_usd: float = Field(ge=0.0)
    provider: str = "openai"
    json_mode: str = "json_schema"      # json_schema | prompt_coerced


class ProviderInfo(_Base):
    """Describes one inference provider and its capability surface (F3)."""
    name: str
    base_url: str | None
    default_model: str
    supports_tools: bool
    supports_json_schema: bool


class InferenceComparison(_Base):
    """Side-by-side comparison of one task across providers (F3)."""
    task: str
    rows: list[dict]   # provider, model, latency_ms, tokens, est_cost_usd, output_preview, error?
