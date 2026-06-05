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
from pydantic import BaseModel, Field


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
