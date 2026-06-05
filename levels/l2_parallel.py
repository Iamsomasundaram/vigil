"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  VIGIL — Level 2: Parallel Agent Fan-out                                   ║
║                                                                              ║
║  Four specialist agents analyse the same CVE simultaneously.                 ║
║  A moderator then reads all four reports and produces a final verdict.       ║
╚══════════════════════════════════════════════════════════════════════════════╝

CONCEPTS COVERED
────────────────
  1. async/await        — non-blocking LLM calls
  2. asyncio.gather()   — running multiple coroutines in parallel
  3. Agent personas     — same model, different system prompts = different experts
  4. Fan-out pattern    — one input → many parallel analyses
  5. Aggregation        — combining multiple outputs into one final verdict
  6. Sequential + Parallel together — parallel fan-out THEN sequential synthesis

WHY PARALLEL?
─────────────
  Sequential (L1 style):
    Agent1 (3s) → Agent2 (3s) → Agent3 (3s) → Agent4 (3s) = 12 seconds

  Parallel (this level):
    Agent1 ─┐
    Agent2 ─┤ all at once = 3 seconds
    Agent3 ─┤
    Agent4 ─┘

  For a 15-agent committee, the difference is 45 seconds vs 3 seconds.
  At scale, parallel execution is not optional — it's mandatory.

WHAT IS AN "AGENT"?
────────────────────
  At this level, an "agent" is simply:
    - A system prompt that defines a specialist role
    - A Pydantic model that defines its output shape
    - An async function that calls the LLM with both

  Same model. Same API. Different persona → different analysis.
  That's the power of system prompts.

PATTERN: FAN-OUT + SYNTHESISE
───────────────────────────────
  This is one of the most important patterns in multi-agent AI:

    Input
      │
      ├──→ Agent A ──┐
      ├──→ Agent B ──┤
      ├──→ Agent C ──┤──→ Moderator ──→ Final Output
      └──→ Agent D ──┘

  The moderator sees ALL four perspectives and produces a
  balanced, informed verdict that no single agent could alone.

RUN THIS FILE
─────────────
  python levels/l2_parallel.py
  python levels/l2_parallel.py CVE-2021-44228
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
from rich.columns import Columns
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

load_dotenv(Path(__file__).parent.parent / ".env")

console = Console()


def _strict_schema(model) -> dict:
    """
    Build a JSON schema compatible with OpenAI strict mode:
      - additionalProperties: false  (from ConfigDict extra='forbid')
      - all properties listed in required  (OpenAI strict requires this even for nullable fields)
    """
    schema = model.model_json_schema()
    _apply_required(schema)
    return schema


def _apply_required(schema: dict) -> None:
    """Recursively ensure every object node has all its properties in 'required'."""
    if "properties" in schema:
        schema["required"] = list(schema["properties"].keys())
    for sub in schema.get("$defs", {}).values():
        _apply_required(sub)


class _Base(BaseModel):
    """Base model with additionalProperties=false for OpenAI strict JSON schema mode."""
    model_config = ConfigDict(extra="forbid")

# ─── ASYNC CLIENT ─────────────────────────────────────────────────────────────
# AsyncOpenAI is the async version of the OpenAI client.
# It lets us use `await` so multiple calls can run concurrently.
# Regular OpenAI client = blocks while waiting → sequential
# AsyncOpenAI client   = yields control while waiting → parallel
client = AsyncOpenAI(timeout=60.0)
MODEL  = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# ─── TOKEN USAGE TRACKING ─────────────────────────────────────────────────────
_usage: dict = {"prompt_tokens": 0, "completion_tokens": 0}

def _reset_usage() -> None:
    global _usage
    _usage = {"prompt_tokens": 0, "completion_tokens": 0}

def _track(response) -> None:
    if hasattr(response, "usage") and response.usage:
        _usage["prompt_tokens"]     += response.usage.prompt_tokens or 0
        _usage["completion_tokens"] += response.usage.completion_tokens or 0

def get_usage() -> dict:
    pt   = _usage["prompt_tokens"]
    ct   = _usage["completion_tokens"]
    cost = (pt * 0.150 + ct * 0.600) / 1_000_000
    return {
        "prompt_tokens":      pt,
        "completion_tokens":  ct,
        "total_tokens":       pt + ct,
        "estimated_cost_usd": round(cost, 6),
    }


# ─── AGENT OUTPUT SCHEMAS ─────────────────────────────────────────────────────
# Each agent returns a different Pydantic model tailored to its specialty.

class ExploitabilityReport(_Base):
    """Exploitability Agent: How easy is this to attack right now?"""
    attack_complexity:          Literal["Low", "High"]
    privileges_required:        Literal["None", "Low", "High"]
    user_interaction_required:  bool
    public_exploit_available:   bool
    actively_exploited_in_wild: bool
    exploitability_score:       float = Field(ge=0.0, le=10.0)
    key_finding:                str   = Field(description="One sentence summary")


class ImpactReport(_Base):
    """Impact Agent: If exploited, what breaks and how badly?"""
    confidentiality_impact: Literal["None", "Low", "High"]
    integrity_impact:       Literal["None", "Low", "High"]
    availability_impact:    Literal["None", "Low", "High"]
    blast_radius:           Literal["Single Host", "Internal Network", "Whole Organisation"]
    data_types_at_risk:     list[str]
    impact_score:           float = Field(ge=0.0, le=10.0)
    key_finding:            str   = Field(description="One sentence summary")


class PatchReport(_Base):
    """Patch Agent: Is there a fix, and what does applying it cost?"""
    patch_available:           bool
    patched_version:           str | None = None
    workaround_available:      bool
    workaround_description:    str | None = None
    patch_complexity:          Literal["Low", "Medium", "High"]
    estimated_downtime_needed: bool
    key_finding:               str = Field(description="One sentence summary")


class BusinessReport(_Base):
    """Business Impact Agent: What is the organisational exposure?"""
    affected_service_types:           list[str]
    business_risk_level:              Literal["Critical", "High", "Medium", "Low"]
    compliance_frameworks_impacted:   list[str]
    customer_data_at_risk:            bool
    key_finding:                      str = Field(description="One sentence summary")


class FinalVerdict(_Base):
    """Moderator: Reads all four reports and makes the final call."""
    overall_priority:       Literal["Critical", "High", "Medium", "Low"]
    recommended_sla_days:   int = Field(ge=0, description="Days to patch deadline")
    executive_summary:      str = Field(description="3-4 sentences for management")
    top_three_actions:      list[str] = Field(description="What to do first, second, third")
    confidence:             Literal["Low", "Medium", "High"]


# ─── AGENT DEFINITIONS ────────────────────────────────────────────────────────
# An agent is just a system prompt + an output schema.
# We define them as a simple dict for readability.

AGENTS = [
    {
        "name":    "Exploitability Agent",
        "system":  "You are a penetration tester. Assess how easy this CVE is to exploit. Focus on attack complexity, required privileges, and whether exploit code is publicly available.",
        "schema":  ExploitabilityReport,
    },
    {
        "name":    "Impact Agent",
        "system":  "You are a security architect. Assess the blast radius and data exposure if this CVE is successfully exploited. Focus on CIA triad impacts.",
        "schema":  ImpactReport,
    },
    {
        "name":    "Patch Agent",
        "system":  "You are a patch management specialist. Assess the availability and complexity of fixes for this CVE. Focus on practical remediation guidance.",
        "schema":  PatchReport,
    },
    {
        "name":    "Business Impact Agent",
        "system":  "You are a risk manager. Assess the business and compliance exposure from this CVE. Focus on affected services, regulatory implications, and customer data risk.",
        "schema":  BusinessReport,
    },
]


# ─── CORE ASYNC FUNCTIONS ─────────────────────────────────────────────────────

async def run_agent(agent: dict, cve_id: str) -> tuple[str, BaseModel]:
    """
    Run a single agent asynchronously.

    Returns (agent_name, result) so we know which output belongs to which agent
    after asyncio.gather() collects everything.

    The `await` keyword is crucial here:
      Without await: the call blocks — other agents must wait
      With await:    Python can context-switch to other agents while waiting
                     for the API response
    """
    schema = agent["schema"]
    response = await client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": agent["system"]},
            {"role": "user",   "content": f"Analyse this CVE: {cve_id}"},
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name":   schema.__name__,
                "strict": True,
                "schema": _strict_schema(schema),
            },
        },
        temperature=0.1,
        max_tokens=4096,
    )
    _track(response)
    result = schema.model_validate(json.loads(response.choices[0].message.content))
    return agent["name"], result


async def run_moderator(cve_id: str, reports: dict) -> FinalVerdict:
    """
    The moderator runs AFTER all four agents complete.
    It receives all four reports as context and produces the final verdict.

    This is the "sequential after parallel" part of the pattern:
      parallel fan-out → wait for all → sequential synthesis
    """
    # Build a summary of all four agent reports to pass as context
    context = f"CVE being assessed: {cve_id}\n\n"
    for agent_name, report in reports.items():
        context += f"=== {agent_name} ===\n"
        for field, value in report.model_dump().items():
            context += f"  {field}: {value}\n"
        context += "\n"

    response = await client.chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are the chief security officer. You have received reports from four specialist agents. "
                    "Synthesise their findings into a final, balanced verdict with clear action priorities."
                ),
            },
            {
                "role": "user",
                "content": f"Based on these four specialist reports, provide the final verdict:\n\n{context}",
            },
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name":   "FinalVerdict",
                "strict": True,
                "schema": _strict_schema(FinalVerdict),
            },
        },
        temperature=0.2,
        max_tokens=4096,
    )
    _track(response)
    return FinalVerdict.model_validate(json.loads(response.choices[0].message.content))


async def analyse_cve(cve_id: str) -> tuple[dict, FinalVerdict]:
    """
    The full fan-out + synthesis pipeline.

    Step 1: Run all four agents IN PARALLEL using asyncio.gather()
    Step 2: Collect their results into a dict
    Step 3: Run the moderator SEQUENTIALLY after all four complete

    asyncio.gather(*coroutines) is the key call:
      - Takes any number of coroutines
      - Starts all of them immediately
      - Waits until ALL of them finish
      - Returns their results in the same order they were passed
    """
    _reset_usage()
    console.print(f"\n[dim]  Launching 4 agents in parallel...[/dim]")

    # ── Fan-out: all four agents start simultaneously ──────────────────────
    start = time.perf_counter()

    results = await asyncio.gather(
        *[run_agent(agent, cve_id) for agent in AGENTS]
        # ↑ This creates 4 coroutines and runs them all at once.
        # Each yields control while waiting for the API, letting the others run.
    )

    elapsed = time.perf_counter() - start
    console.print(f"[dim]  All 4 agents completed in {elapsed:.1f}s[/dim]")

    # Convert list of (name, result) tuples into a dict
    agent_reports = {name: report for name, report in results}

    # ── Synthesis: moderator runs after all agents complete ────────────────
    console.print(f"[dim]  Running moderator...[/dim]")
    verdict = await run_moderator(cve_id, agent_reports)

    return agent_reports, verdict


# ─── DISPLAY HELPERS ──────────────────────────────────────────────────────────

PRIORITY_COLOUR = {"Critical": "bold red", "High": "red", "Medium": "yellow", "Low": "green"}

def display_agent_cards(reports: dict) -> None:
    cards = []
    for agent_name, report in reports.items():
        data = report.model_dump()
        t = Table(box=box.SIMPLE, show_header=False, padding=(0, 1), width=38)
        t.add_column(style="dim", width=18)
        t.add_column()
        for field, value in data.items():
            if field == "key_finding":
                continue
            label = field.replace("_", " ").title()
            val   = str(value) if not isinstance(value, list) else ", ".join(str(v) for v in value)
            t.add_row(label, val)
        finding = data.get("key_finding", "")
        cards.append(Panel(
            f"{t}\n[italic dim]{finding}[/italic dim]",
            title=f"[bold]{agent_name}[/bold]",
            border_style="blue",
            width=42,
        ))
    console.print(Columns(cards, equal=True))


def display_verdict(verdict: FinalVerdict) -> None:
    colour = PRIORITY_COLOUR.get(verdict.overall_priority, "white")
    lines = [
        f"[{colour}][bold]Priority:  {verdict.overall_priority}[/bold][/{colour}]   "
        f"SLA: patch within [bold]{verdict.recommended_sla_days} days[/bold]   "
        f"Confidence: {verdict.confidence}",
        "",
        verdict.executive_summary,
        "",
        "[bold]Top 3 actions:[/bold]",
    ]
    for i, action in enumerate(verdict.top_three_actions, 1):
        lines.append(f"  [bold cyan]{i}.[/bold cyan] {action}")
    console.print(Panel(
        "\n".join(lines),
        title="[bold]Moderator — Final Verdict[/bold]",
        border_style=colour.replace("bold ", ""),
        padding=(1, 2),
    ))


# ─── ENTRY POINT ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    cve_id = sys.argv[1] if len(sys.argv) > 1 else "CVE-2021-44228"

    console.print()
    console.print(f"[bold cyan]VIGIL[/bold cyan] [dim]— Level 2: Parallel Agent Fan-out[/dim]")
    console.print(f"[dim]Model: {MODEL}  |  CVE: {cve_id}  |  4 parallel agents + 1 moderator[/dim]")

    # asyncio.run() is the entry point for async code.
    # It creates an event loop, runs the coroutine, and shuts down cleanly.
    reports, verdict = asyncio.run(analyse_cve(cve_id))

    console.print()
    display_agent_cards(reports)
    console.print()
    display_verdict(verdict)
    console.print()
