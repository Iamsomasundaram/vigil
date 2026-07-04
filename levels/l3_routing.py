"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  VIGIL — Level 3: Conditional Routing                                      ║
║                                                                              ║
║  A router agent reads the CVE and decides WHICH analysis track to run.      ║
║  Different threats warrant different response depths and urgencies.          ║
╚══════════════════════════════════════════════════════════════════════════════╝

CONCEPTS COVERED
────────────────
  1. Router pattern          — LLM as a control-flow decision maker
  2. Conditional dispatch    — structured output determines which code path runs
  3. Track-based execution   — different pipelines for different situations
  4. Composing levels        — L3 reuses L2 fan-out for its most critical track
  5. The "right tool for the job" principle — not every CVE needs a full L2 run

WHY ROUTING?
────────────
  Without routing, every CVE triggers the same analysis pipeline regardless
  of its actual threat level:
    CVE-2021-44228 (Log4Shell, CVSS 10.0)   → full L2 run (correct ✓)
    CVE-2023-12345 (low-severity info-leak) → full L2 run (overkill ✗)
    CVE-2022-99999 (poorly documented)      → full L2 run (wasteful ✗)

  With routing, the system adapts:
    Critical / actively exploited           → CRITICAL TRACK  (full fan-out)
    Patch available, moderate impact        → PATCH TRACK     (focused analysis)
    Low severity, no known exploits         → MONITOR TRACK   (lightweight summary)
    Ambiguous, conflicting data, novel CVE  → HUMAN REVIEW    (escalate to human)

  This saves cost, reduces latency for low-priority items, and—critically—
  reserves expensive deep-dives for the threats that actually need them.

THE KEY INSIGHT: LLM AS CONTROL FLOW
──────────────────────────────────────
  In traditional programming, control flow is deterministic:
    if cvss_score >= 9.0: run_critical_path()

  The problem: CVSS scores are a proxy. A CVSS 7.5 vulnerability actively
  exploited in the wild is more urgent than a CVSS 9.0 with no public exploit.
  Severity labels miss nuance that plain text captures.

  With a routing agent, the LLM reads the full CVE context—description,
  exploitation status, patch availability, affected ecosystem—and reasons
  about which track to use. It's not a lookup table; it's judgement.

  The output is still structured (a Pydantic model with a `track` field),
  so the routing decision is deterministic code:
    routing = await router_agent(cve_id)         # LLM makes the judgment
    result  = await TRACKS[routing.track](...)   # Python executes the path

PATTERN: ROUTER → TRACK → RESULT
──────────────────────────────────
  Input
    │
    ▼
  ┌─────────────────┐
  │  Router Agent   │   "What kind of threat is this? Which track fits?"
  └────────┬────────┘
           │ RoutingDecision.track = "critical_response" | "standard_patch"
           │                       | "low_risk_monitor"  | "needs_human_review"
           │
    ┌──────┴──────────────────────────────────────┐
    │              │              │               │
    ▼              ▼              ▼               ▼
  Critical      Patch         Monitor        Human Review
  (2 parallel   (single       (lightweight    (flag + key
   agents +     focused       summary +       questions for
   synthesis)   report)       next action)    analyst)
    │              │              │               │
    └──────────────┴──────────────┴───────────────┘
                          │
                          ▼
                    Typed Result

RUN THIS FILE
─────────────
  python levels/l3_routing.py
  python levels/l3_routing.py CVE-2023-44487
  python levels/l3_routing.py CVE-2014-0160
"""

import asyncio
import json
import os
import sys
import time
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from openai import AsyncOpenAI
from pydantic import BaseModel, ConfigDict, Field
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box
from vigil.inference import acomplete_json

load_dotenv(Path(__file__).parent.parent / ".env")

console = Console()

# Using AsyncOpenAI so track handlers can run async sub-agents (e.g. critical
# track fans out two agents in parallel, same technique as L2).
client = AsyncOpenAI(timeout=60.0)
MODEL  = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# ─── TOKEN USAGE TRACKING ─────────────────────────────────────────────────────
# Accumulates token counts across all OpenAI calls in one run.
# The API reads get_usage() after the level function returns.
# NOTE: module-level state — not safe for concurrent requests,
#       which is fine for this single-user learning project.

_usage: dict = {"prompt_tokens": 0, "completion_tokens": 0}

def _reset_usage() -> None:
    """Clear accumulated token counts. Call at the start of each run."""
    global _usage
    _usage = {"prompt_tokens": 0, "completion_tokens": 0}

def _track(response) -> None:
    """Add this response's token usage to the accumulator."""
    if hasattr(response, "usage") and response.usage:
        _usage["prompt_tokens"]     += response.usage.prompt_tokens or 0
        _usage["completion_tokens"] += response.usage.completion_tokens or 0

def get_usage() -> dict:
    """Return accumulated token counts and estimated cost for the last run.

    Pricing: gpt-4o-mini (April 2025)
      Input:  $0.150 per 1M tokens
      Output: $0.600 per 1M tokens
    """
    pt   = _usage["prompt_tokens"]
    ct   = _usage["completion_tokens"]
    cost = (pt * 0.150 + ct * 0.600) / 1_000_000
    return {
        "prompt_tokens":      pt,
        "completion_tokens":  ct,
        "total_tokens":       pt + ct,
        "estimated_cost_usd": round(cost, 6),
    }


# ─── SCHEMA HELPER ────────────────────────────────────────────────────────────
# OpenAI strict mode requires:
#   1. additionalProperties: false  — enforced by ConfigDict(extra="forbid")
#   2. ALL properties in "required" — enforced by _apply_required() below
#
# Why strict mode matters:
#   Without it, the model can omit fields or return unexpected keys.
#   With it, the response is guaranteed to match your schema exactly.

def _strict_schema(model) -> dict:
    """Return a JSON schema fully compatible with OpenAI strict mode."""
    schema = model.model_json_schema()
    _apply_required(schema)
    return schema


def _apply_required(schema: dict) -> None:
    """Recursively add all property names to 'required' at every object level."""
    if "properties" in schema:
        schema["required"] = list(schema["properties"].keys())
    for sub in schema.get("$defs", {}).values():
        _apply_required(sub)


class _Base(BaseModel):
    """Shared base: extra='forbid' adds additionalProperties=false to JSON schema."""
    model_config = ConfigDict(extra="forbid")


# ─── ROUTING SCHEMA ───────────────────────────────────────────────────────────
# The router agent returns exactly this shape.
#
# `track` is the most important field — it controls which code path runs next.
# Using Literal["..."] means the model MUST return one of these exact strings.
# No ambiguity, no typos, no "slightly-different-wording" to parse.
#
# `urgency_hours` gives the router's view on how long the team has to act.
# This is separate from track — a "standard_patch" CVE might still be urgent
# if the patch is trivial and the blast radius is large.

class RoutingDecision(_Base):
    """Router agent output: which track to run and why."""
    track: Literal[
        "critical_response",  # Actively exploited or CVSS ≥9; run full analysis
        "standard_patch",     # Patch available, moderate impact; focus on remediation
        "low_risk_monitor",   # Low severity, no known exploits; log and review later
        "needs_human_review", # Ambiguous, poorly documented, or novel threat class
    ]
    reason:        str = Field(description="One sentence: why this track was chosen")
    urgency_hours: int = Field(ge=0, description="Estimated hours before action required")
    confidence:    Literal["High", "Medium", "Low"]


# ─── TRACK OUTPUT SCHEMAS ─────────────────────────────────────────────────────
# Each track produces a different output shape tailored to its use case.
# The caller receives both the RoutingDecision and one of these four types.

class CriticalReport(_Base):
    """
    Track: critical_response
    Full fan-out: exploitability + impact assessed in parallel, then synthesised.
    Used when immediate action is required.
    """
    exploitability_summary: str   = Field(description="How easy is exploitation? Any public PoC?")
    impact_summary:         str   = Field(description="CIA triad impacts if successfully exploited")
    blast_radius:           Literal["Single Host", "Internal Network", "Whole Organisation"]
    immediate_actions:      list[str] = Field(description="Do these in the next hour")
    patch_guidance:         str   = Field(description="Specific version to upgrade to, or workaround")
    escalate_to_ciso:       bool


class PatchReport(_Base):
    """
    Track: standard_patch
    Focused on remediation — patch availability, effort, and business window.
    Used when the fix path is clear and impact is contained.
    """
    patch_available:    bool
    patched_version:    str  = Field(description="Version that resolves the CVE, or 'None'")
    workaround:         str  = Field(description="Interim workaround if no patch yet, or 'None'")
    patch_complexity:   Literal["Low", "Medium", "High"]
    downtime_required:  bool
    recommended_window: str  = Field(description="e.g. 'next maintenance window' or 'within 7 days'")
    key_finding:        str  = Field(description="One sentence for the ticket summary")


class MonitorSummary(_Base):
    """
    Track: low_risk_monitor
    Lightweight. Just enough to log the CVE and set a review date.
    Used for low-severity items that don't warrant immediate action.
    """
    why_low_risk:       str  = Field(description="One sentence: why this is low priority")
    affected_component: str
    review_in_days:     int  = Field(ge=1, description="When to re-evaluate this CVE")
    watch_for:          str  = Field(description="What signal would upgrade this to a higher track")


class HumanReviewFlag(_Base):
    """
    Track: needs_human_review
    Raised when the router lacks confidence or the CVE doesn't fit standard patterns.
    A human analyst should investigate before any automated action is taken.
    """
    reason_for_escalation: str       = Field(description="Why automation shouldn't handle this alone")
    known_facts:           list[str] = Field(description="What is known about this CVE so far")
    questions_for_analyst: list[str] = Field(description="Specific questions an analyst should answer")
    suggested_resources:   list[str] = Field(description="NVD link, vendor advisory, EPSS score, etc.")


# ─── ROUTER AGENT ─────────────────────────────────────────────────────────────
# The router is just another LLM call — but its output controls program flow.
# This is what makes it a "routing agent" rather than a plain API call.

async def run_router(cve_id: str) -> RoutingDecision:
    """
    Ask the LLM: 'Given this CVE, which response track should we follow?'

    The model reasons about severity, exploitation status, patch availability,
    and affected ecosystem — then returns a structured RoutingDecision.

    Crucially, the `track` field isn't a score or probability; it's a named
    decision that maps directly onto a code path. This makes routing
    deterministic once the LLM has decided.
    """
    payload, usage = await acomplete_json(
        client=client,
        task="route",
        schema_model=RoutingDecision,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a security triage specialist. Your job is to classify incoming CVEs "
                    "and route them to the correct response track. "
                    "Be decisive — pick the single most appropriate track. "
                    "Prefer 'critical_response' for anything actively exploited in the wild. "
                    "Use 'needs_human_review' only when key facts are genuinely unknown or contradictory."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Classify this CVE and decide which response track it requires: {cve_id}\n\n"
                    "Tracks:\n"
                    "  critical_response  — CVSS ≥9 OR actively exploited in the wild\n"
                    "  standard_patch     — patch available, moderate impact, no active exploitation\n"
                    "  low_risk_monitor   — CVSS <5, no known exploits, limited blast radius\n"
                    "  needs_human_review — novel, ambiguous, or insufficient public data\n"
                ),
            },
        ],
        temperature=0.1,
        max_tokens=512,
    )
    _usage["prompt_tokens"] += usage.prompt_tokens
    _usage["completion_tokens"] += usage.completion_tokens
    return RoutingDecision.model_validate(payload)


# ─── TRACK HANDLERS ───────────────────────────────────────────────────────────
# Each handler is an async function that receives the CVE ID and the routing
# decision (so it knows the router's reasoning) and returns a typed report.
#
# Notice the pattern: the routing decision is passed INTO the handler.
# The handler can use `routing.reason` in its prompt to give the specialist
# context about WHY this track was chosen — avoiding redundant re-analysis.

async def handle_critical(cve_id: str, routing: RoutingDecision) -> CriticalReport:
    """
    Critical track: runs two agents in parallel (mirroring L2's fan-out),
    then asks a synthesis agent to produce actionable output.

    We fan out exploitability + impact simultaneously, then a third call
    synthesises them into a CriticalReport. Total latency ≈ max(call1, call2) + call3.
    """

    # ── Sub-agent 1: Exploitability ───────────────────────────────────────────
    async def _exploitability() -> str:
        r = await client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": "You are a penetration tester. Assess exploitability."},
                {"role": "user",   "content": f"How easy is {cve_id} to exploit? Any public PoC or active exploitation?"},
            ],
            temperature=0.1,
            max_tokens=400,
        )
        _track(r)
        return r.choices[0].message.content

    # ── Sub-agent 2: Impact ───────────────────────────────────────────────────
    async def _impact() -> str:
        r = await client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": "You are a security architect. Assess blast radius and CIA triad impact."},
                {"role": "user",   "content": f"If {cve_id} is exploited, what breaks? How widely?"},
            ],
            temperature=0.1,
            max_tokens=400,
        )
        _track(r)
        return r.choices[0].message.content

    # Run both sub-agents in parallel — L2's asyncio.gather() pattern applied here
    exploitability_text, impact_text = await asyncio.gather(_exploitability(), _impact())

    # ── Synthesis: combine both analyses into a structured CriticalReport ─────
    response = await client.chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a security incident commander. Synthesise the specialist findings "
                    "into a clear, actionable critical response report."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"CVE: {cve_id}\n"
                    f"Router classification: {routing.reason}\n\n"
                    f"Exploitability analysis:\n{exploitability_text}\n\n"
                    f"Impact analysis:\n{impact_text}\n\n"
                    "Produce the critical response report."
                ),
            },
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name":   "CriticalReport",
                "strict": True,
                "schema": _strict_schema(CriticalReport),
            },
        },
        temperature=0.1,
        max_tokens=2048,
    )
    _track(response)
    return CriticalReport.model_validate(
        json.loads(response.choices[0].message.content)
    )


async def handle_standard_patch(cve_id: str, routing: RoutingDecision) -> PatchReport:
    """
    Patch track: single focused call on remediation.
    The router already determined risk is contained — we just need the fix path.
    """
    response = await client.chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "system",
                "content": "You are a patch management specialist. Focus on practical remediation.",
            },
            {
                "role": "user",
                "content": (
                    f"CVE: {cve_id}\n"
                    f"Context: {routing.reason}\n\n"
                    "Provide patch availability, complexity, and recommended remediation window."
                ),
            },
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name":   "PatchReport",
                "strict": True,
                "schema": _strict_schema(PatchReport),
            },
        },
        temperature=0.1,
        max_tokens=1024,
    )
    _track(response)
    return PatchReport.model_validate(
        json.loads(response.choices[0].message.content)
    )


async def handle_low_risk(cve_id: str, routing: RoutingDecision) -> MonitorSummary:
    """
    Monitor track: lightest possible analysis.
    Log the CVE, record when to review it again, note what would escalate it.
    """
    response = await client.chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "system",
                "content": "You are a security analyst managing a low-risk vulnerability backlog.",
            },
            {
                "role": "user",
                "content": (
                    f"CVE: {cve_id}\n"
                    f"Context: {routing.reason}\n\n"
                    "Summarise why this is low priority and when to review it next."
                ),
            },
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name":   "MonitorSummary",
                "strict": True,
                "schema": _strict_schema(MonitorSummary),
            },
        },
        temperature=0.1,
        max_tokens=512,
    )
    _track(response)
    return MonitorSummary.model_validate(
        json.loads(response.choices[0].message.content)
    )


async def handle_human_review(cve_id: str, routing: RoutingDecision) -> HumanReviewFlag:
    """
    Human review track: automation stops here.
    The output is a structured brief for a human analyst — not a final decision.

    This is an important safety pattern: when the AI is uncertain, it doesn't
    guess and act. It escalates with a clear explanation of what it knows and
    what questions need human judgement.
    """
    response = await client.chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a security triage coordinator. "
                    "This CVE requires human review before any automated action. "
                    "Prepare a clear brief for the analyst."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"CVE: {cve_id}\n"
                    f"Reason flagged for review: {routing.reason}\n\n"
                    "List what is known, what is uncertain, and what questions the analyst must answer."
                ),
            },
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name":   "HumanReviewFlag",
                "strict": True,
                "schema": _strict_schema(HumanReviewFlag),
            },
        },
        temperature=0.2,   # Slightly higher — we want the questions to be varied and thorough
        max_tokens=1024,
    )
    _track(response)
    return HumanReviewFlag.model_validate(
        json.loads(response.choices[0].message.content)
    )


# ─── DISPATCH TABLE ───────────────────────────────────────────────────────────
# A dict that maps track names to handler functions.
#
# This is cleaner than a chain of if/elif — adding a new track means adding
# one entry here and one handler function, not modifying a nested if block.
#
# Type: dict[str, async callable(cve_id, routing) → BaseModel]

TRACK_HANDLERS = {
    "critical_response":  handle_critical,
    "standard_patch":     handle_standard_patch,
    "low_risk_monitor":   handle_low_risk,
    "needs_human_review": handle_human_review,
}


# ─── MAIN PIPELINE ────────────────────────────────────────────────────────────

async def analyse_cve(cve_id: str) -> tuple[RoutingDecision, _Base]:
    """
    Full L3 pipeline: route → dispatch → handle.

    Step 1: Router agent reads the CVE and returns a RoutingDecision.
    Step 2: The track field selects a handler from TRACK_HANDLERS.
    Step 3: The handler runs its specific pipeline and returns a typed report.

    The caller receives both objects so it can display the routing reasoning
    alongside the final report — transparency about why a track was chosen
    is important for trust and auditability.
    """
    _reset_usage()
    console.print(f"\n[dim]  Running router agent...[/dim]")

    start_router = time.perf_counter()
    routing = await run_router(cve_id)
    router_ms = int((time.perf_counter() - start_router) * 1000)

    console.print(
        f"[dim]  Routed to [bold]{routing.track}[/bold] "
        f"(confidence: {routing.confidence}, {router_ms}ms)[/dim]"
    )
    console.print(f"[dim]  Running {routing.track} handler...[/dim]")

    # ── Key line: LLM output drives Python control flow ────────────────────
    handler = TRACK_HANDLERS[routing.track]    # look up the right function
    result  = await handler(cve_id, routing)   # run it

    return routing, result


# ─── DISPLAY HELPERS ──────────────────────────────────────────────────────────

TRACK_COLOURS = {
    "critical_response":  "bold red",
    "standard_patch":     "yellow",
    "low_risk_monitor":   "green",
    "needs_human_review": "magenta",
}

TRACK_LABELS = {
    "critical_response":  "CRITICAL RESPONSE",
    "standard_patch":     "STANDARD PATCH",
    "low_risk_monitor":   "LOW RISK — MONITOR",
    "needs_human_review": "HUMAN REVIEW REQUIRED",
}


def display_routing(routing: RoutingDecision) -> None:
    colour = TRACK_COLOURS.get(routing.track, "white")
    label  = TRACK_LABELS.get(routing.track, routing.track)

    t = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
    t.add_column(style="dim", width=18)
    t.add_column()
    t.add_row("Track",      f"[{colour}][bold]{label}[/bold][/{colour}]")
    t.add_row("Reason",     routing.reason)
    t.add_row("Act within", f"{routing.urgency_hours}h")
    t.add_row("Confidence", routing.confidence)
    console.print(Panel(t, title="[bold]Router Decision[/bold]", border_style="cyan"))


def display_result(routing: RoutingDecision, result: _Base) -> None:
    colour = TRACK_COLOURS.get(routing.track, "white")
    data   = result.model_dump()

    # Each track renders slightly differently to highlight what matters most.
    if routing.track == "critical_response":
        lines = []
        lines.append(f"[bold]Blast radius:[/bold] [{colour}]{data['blast_radius']}[/{colour}]")
        lines.append(f"[bold]Escalate to CISO:[/bold] {'[bold red]YES[/bold red]' if data['escalate_to_ciso'] else 'No'}")
        lines.append("")
        lines.append(f"[bold]Exploitability:[/bold] {data['exploitability_summary']}")
        lines.append("")
        lines.append(f"[bold]Impact:[/bold] {data['impact_summary']}")
        lines.append("")
        lines.append("[bold]Immediate actions:[/bold]")
        for action in data["immediate_actions"]:
            lines.append(f"  [red]•[/red] {action}")
        lines.append("")
        lines.append(f"[bold]Patch guidance:[/bold] {data['patch_guidance']}")

    elif routing.track == "standard_patch":
        lines = []
        patch_status = f"[green]{data['patched_version']}[/green]" if data["patch_available"] else "[yellow]Not yet available[/yellow]"
        lines.append(f"[bold]Patch available:[/bold] {patch_status}")
        lines.append(f"[bold]Workaround:[/bold] {data['workaround']}")
        lines.append(f"[bold]Complexity:[/bold] {data['patch_complexity']}  |  Downtime needed: {data['downtime_required']}")
        lines.append(f"[bold]Window:[/bold] {data['recommended_window']}")
        lines.append("")
        lines.append(f"[dim]{data['key_finding']}[/dim]")

    elif routing.track == "low_risk_monitor":
        lines = []
        lines.append(f"[bold]Component:[/bold] {data['affected_component']}")
        lines.append(f"[bold]Why low risk:[/bold] {data['why_low_risk']}")
        lines.append(f"[bold]Review in:[/bold] {data['review_in_days']} days")
        lines.append(f"[bold]Watch for:[/bold] {data['watch_for']}")

    else:  # needs_human_review
        lines = []
        lines.append(f"[bold]Reason for escalation:[/bold] {data['reason_for_escalation']}")
        lines.append("")
        lines.append("[bold]Known facts:[/bold]")
        for fact in data["known_facts"]:
            lines.append(f"  [cyan]•[/cyan] {fact}")
        lines.append("")
        lines.append("[bold]Questions for analyst:[/bold]")
        for q in data["questions_for_analyst"]:
            lines.append(f"  [magenta]?[/magenta] {q}")

    console.print(Panel(
        "\n".join(lines),
        title=f"[bold]{TRACK_LABELS.get(routing.track, routing.track)} — Analysis[/bold]",
        border_style=colour.replace("bold ", ""),
        padding=(1, 2),
    ))


# ─── ENTRY POINT ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    cve_id = sys.argv[1] if len(sys.argv) > 1 else "CVE-2021-44228"

    console.print()
    console.print(Text("VIGIL", style="bold cyan") + Text(" — Level 3: Conditional Routing", style="dim"))
    console.print(f"[dim]Model: {MODEL}  |  CVE: {cve_id}[/dim]")

    routing, result = asyncio.run(analyse_cve(cve_id))

    console.print()
    display_routing(routing)
    console.print()
    display_result(routing, result)
    console.print()

    # ── Try a second CVE to see the router pick a different track ──────────
    # Uncomment to compare routing decisions across threat levels:
    # routing2, result2 = asyncio.run(analyse_cve("CVE-2014-0160"))  # Heartbleed
    # routing3, result3 = asyncio.run(analyse_cve("CVE-2023-12345"))  # hypothetical low risk
