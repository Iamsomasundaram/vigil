"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  VIGIL — Architecture 2: Plan-and-Execute                                  ║
║                                                                              ║
║  The agent first builds a complete investigation plan, then executes each   ║
║  step independently — planning and execution are strictly separated.        ║
╚══════════════════════════════════════════════════════════════════════════════╝

WHAT IS PLAN-AND-EXECUTE?
──────────────────────────
  Plan-and-Execute splits agent work into two distinct phases:

    PHASE 1 — PLAN
    ┌──────────────────────────────────────────────────────────────────────┐
    │  Given the goal, produce a complete, ordered list of steps.          │
    │  Don't do anything yet — just plan.                                  │
    │                                                                      │
    │  Example plan for "Assess CVE-2021-44228":                           │
    │    Step 1: Fetch NVD data to get CVSS score and description          │
    │    Step 2: Fetch EPSS score to assess exploitation likelihood        │
    │    Step 3: Check CISA KEV for confirmed active exploitation          │
    │    Step 4: Synthesise all findings into a risk verdict               │
    └──────────────────────────────────────────────────────────────────────┘

    PHASE 2 — EXECUTE
    ┌──────────────────────────────────────────────────────────────────────┐
    │  Work through the plan step by step.                                 │
    │  Each step gets fresh context: the original goal + prior results.   │
    │  Steps can be re-planned if a result changes the picture.            │
    └──────────────────────────────────────────────────────────────────────┘

HOW PLAN-AND-EXECUTE DIFFERS FROM ReAct
─────────────────────────────────────────
  ReAct (A1):
    • Interleaves thinking and acting
    • Decides the next step AFTER seeing the previous result
    • Reactive — course corrects as new information arrives
    • Can be hard to predict or control

  Plan-and-Execute (A2):
    • Separates thinking from acting entirely
    • Makes ALL decisions upfront in the planning phase
    • Deterministic — the same goal produces the same plan
    • Easy to inspect, modify, and override before execution begins

  Neither is universally better. ReAct is more adaptive; Plan-and-Execute
  is more predictable and easier to audit.

WHY SEPARATE PLANNING FROM EXECUTION?
───────────────────────────────────────
  1. Human oversight — you can review (and reject) the plan before anything
     runs. In security workflows, this is important: "The agent plans to
     quarantine this host — approve?" is better than learning after the fact.

  2. Parallelism — steps that don't depend on each other can run in parallel
     once the plan is produced. A planner might produce 3 independent data
     fetches that all run simultaneously.

  3. Cost control — planning uses one cheap LLM call. If the plan is bad,
     you discard it without paying for execution.

  4. Re-planning — if step 3 fails, you can ask the planner to revise the
     remaining steps given the new situation.

THE EXECUTION MODEL
────────────────────
  Each step in the plan is one of:
    • tool_call  — call a named tool (fetch_nvd_data, fetch_epss_score, etc.)
    • synthesise — no tool; use accumulated results to produce the final report

  The executor runs steps sequentially, collecting observations.
  All observations are passed to the final synthesis step.

RUN THIS FILE
─────────────
  python architectures/a2_plan_execute.py
  python architectures/a2_plan_execute.py CVE-2023-44487
  python architectures/a2_plan_execute.py CVE-2014-0160
"""

import asyncio
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Literal

import httpx
from dotenv import load_dotenv
from openai import AsyncOpenAI
from pydantic import BaseModel, ConfigDict, Field
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box

load_dotenv(Path(__file__).parent.parent / ".env")

console = Console()
client  = AsyncOpenAI(timeout=60.0)
MODEL   = os.getenv("OPENAI_MODEL", "gpt-4o-mini")


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


http = httpx.AsyncClient(timeout=15.0)


# ─── SCHEMA HELPERS ───────────────────────────────────────────────────────────

def _strict_schema(model) -> dict:
    schema = model.model_json_schema()
    _apply_required(schema)
    return schema

def _apply_required(schema: dict) -> None:
    if "properties" in schema:
        schema["required"] = list(schema["properties"].keys())
    for sub in schema.get("$defs", {}).values():
        _apply_required(sub)

class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ─── PLAN SCHEMA ──────────────────────────────────────────────────────────────

class PlanStep(_Base):
    """
    A single step in the investigation plan.

    step_type distinguishes between steps that call tools and the final
    synthesis step that uses accumulated results to write the report.
    """
    step:        int
    description: str  = Field(description="What this step does and why it is needed")
    step_type:   Literal["tool_call", "synthesise"]
    tool_name:   str  = Field(description="Tool to call (empty string if step_type is synthesise)")


class InvestigationPlan(_Base):
    """
    The complete plan produced by the planner LLM call.

    The plan is produced BEFORE any execution. Each step is a discrete unit
    that the executor will carry out in order.
    """
    goal:        str            = Field(description="Restatement of the investigation goal")
    steps:       list[PlanStep] = Field(description="Ordered steps to achieve the goal")
    reasoning:   str            = Field(description="Why these steps, in this order?")


# ─── REPORT SCHEMA ────────────────────────────────────────────────────────────

class PlanExecuteReport(_Base):
    """Final report produced after all plan steps have been executed."""
    cve_id:             str
    cvss_score:         float     = Field(description="From NVD — current base score")
    cvss_severity:      str       = Field(description="Critical / High / Medium / Low")
    epss_score:         float     = Field(ge=0.0, le=1.0)
    epss_percentile:    float     = Field(ge=0.0, le=1.0)
    in_cisa_kev:        bool      = Field(description="Confirmed active exploitation by CISA KEV")
    patch_available:    bool
    risk_verdict:       str       = Field(description="One-sentence risk summary")
    recommended_action: str
    steps_executed:     int       = Field(description="How many plan steps were executed")
    data_sources:       list[str]


# ─── TOOL DEFINITIONS ─────────────────────────────────────────────────────────
# Same three tools as A1 (ReAct). The difference is not in the tools
# but in HOW the agent decides to use them — plan first, then execute.

TOOL_DEFINITIONS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "fetch_nvd_data",
            "description": (
                "Fetches live vulnerability data from the NVD API. "
                "Returns description, CVSS score, severity, and references."
            ),
            "parameters": {
                "type": "object",
                "properties": {"cve_id": {"type": "string"}},
                "required": ["cve_id"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_epss_score",
            "description": (
                "Fetches the EPSS exploitation probability score (0–1, updated daily)."
            ),
            "parameters": {
                "type": "object",
                "properties": {"cve_id": {"type": "string"}},
                "required": ["cve_id"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_cisa_kev",
            "description": (
                "Checks the CISA Known Exploited Vulnerabilities catalog. "
                "Returns whether the CVE is confirmed actively exploited."
            ),
            "parameters": {
                "type": "object",
                "properties": {"cve_id": {"type": "string"}},
                "required": ["cve_id"],
                "additionalProperties": False,
            },
        },
    },
]

AVAILABLE_TOOLS = {d["function"]["name"] for d in TOOL_DEFINITIONS}


# ─── TOOL IMPLEMENTATIONS ─────────────────────────────────────────────────────

async def fetch_nvd_data(cve_id: str) -> dict:
    url = f"https://services.nvd.nist.gov/rest/json/cves/2.0?cveId={cve_id}"
    try:
        r = await http.get(url)
        r.raise_for_status()
        data  = r.json()
        vulns = data.get("vulnerabilities", [])
        if not vulns:
            return {"error": f"{cve_id} not found in NVD"}

        cve          = vulns[0]["cve"]
        descriptions = cve.get("descriptions", [])
        description  = next((d["value"] for d in descriptions if d["lang"] == "en"), "No description")

        metrics    = cve.get("metrics", {})
        cvss_score = severity = None
        for key in ("cvssMetricV31", "cvssMetricV30", "cvssMetricV2"):
            if key in metrics:
                m          = metrics[key][0]["cvssData"]
                cvss_score = m.get("baseScore")
                severity   = m.get("baseSeverity") or metrics[key][0].get("baseSeverity")
                break

        return {
            "source": "NVD", "cve_id": cve_id,
            "description": description, "cvss_score": cvss_score, "severity": severity,
            "published": cve.get("published", "unknown"),
        }
    except Exception as e:
        return {"error": str(e)}


async def fetch_epss_score(cve_id: str) -> dict:
    url = f"https://api.first.org/data/v1/epss?cve={cve_id}"
    try:
        r     = await http.get(url)
        r.raise_for_status()
        items = r.json().get("data", [])
        if not items:
            return {"source": "EPSS", "cve_id": cve_id, "score": None, "note": "Not scored"}
        item  = items[0]
        score = float(item.get("epss", 0))
        pct   = float(item.get("percentile", 0))
        return {
            "source": "EPSS", "cve_id": cve_id,
            "score": score, "percentile": pct,
            "note": f"{score * 100:.1f}% exploitation probability; {pct * 100:.0f}th percentile",
        }
    except Exception as e:
        return {"error": str(e)}


async def check_cisa_kev(cve_id: str) -> dict:
    url = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"
    try:
        r     = await http.get(url)
        r.raise_for_status()
        vulns = r.json().get("vulnerabilities", [])
        match = next((v for v in vulns if v.get("cveID") == cve_id), None)
        if match:
            return {
                "source": "CISA KEV", "cve_id": cve_id, "in_kev": True,
                "date_added": match.get("dateAdded"),
                "due_date":   match.get("dueDate"),
                "required_action": match.get("requiredAction"),
                "note": f"CONFIRMED ACTIVE EXPLOITATION. Added {match.get('dateAdded')}.",
            }
        return {
            "source": "CISA KEV", "cve_id": cve_id, "in_kev": False,
            "note": f"Not in KEV catalog ({len(vulns)} entries checked).",
        }
    except Exception as e:
        return {"error": str(e)}


TOOL_FUNCTIONS: dict[str, Any] = {
    "fetch_nvd_data":   fetch_nvd_data,
    "fetch_epss_score": fetch_epss_score,
    "check_cisa_kev":   check_cisa_kev,
}


# ─── PHASE 1: PLANNING ────────────────────────────────────────────────────────

async def create_plan(cve_id: str) -> InvestigationPlan:
    """
    Phase 1: ask the LLM to produce a complete investigation plan.

    The planner has no tools — it cannot DO anything here.
    It only produces a structured list of steps to execute later.

    This separation is the defining feature of Plan-and-Execute:
    the agent that plans is different from the agent that acts.
    """
    response = await client.chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are an investigation planner for a CVE intelligence system. "
                    "Your ONLY job is to produce a step-by-step plan for investigating a CVE. "
                    "Do NOT execute any steps yourself — just plan. "
                    "\n\n"
                    "Available tools for the executor to use:\n"
                    "  fetch_nvd_data   — get CVSS score, severity, description from NVD\n"
                    "  fetch_epss_score — get exploitation probability (0–1) from EPSS\n"
                    "  check_cisa_kev   — check if CVE is in CISA's active exploit catalog\n"
                    "\n"
                    "Each step must be one of: tool_call (call a tool) or synthesise (final report). "
                    "The last step must always be synthesise. "
                    "Think about what information is needed and in what order."
                ),
            },
            {
                "role": "user",
                "content": f"Create an investigation plan for {cve_id}.",
            },
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name":   "InvestigationPlan",
                "strict": True,
                "schema": _strict_schema(InvestigationPlan),
            },
        },
        temperature=0.1,
        max_tokens=1024,
    )
    _track(response)
    return InvestigationPlan.model_validate(json.loads(response.choices[0].message.content))


# ─── PHASE 2: EXECUTION ───────────────────────────────────────────────────────

async def execute_plan(
    cve_id: str,
    plan: InvestigationPlan,
) -> tuple[PlanExecuteReport, list[dict]]:
    """
    Phase 2: execute each step in the plan.

    The executor is responsible for:
    - Calling the right tool for each tool_call step
    - Passing all accumulated observations to the synthesis step
    - Producing the structured final report

    The executor does NOT re-plan — it executes what the planner decided.
    If a tool fails, the result includes the error and execution continues.
    """
    observations: list[dict] = []  # Accumulates results from every step
    execution_log: list[dict] = []

    for step in plan.steps:
        console.print(
            f"[dim]  Step {step.step}: {step.step_type}"
            + (f" → {step.tool_name}" if step.tool_name else "")
            + f" | {step.description[:60]}[/dim]"
        )

        if step.step_type == "tool_call":
            # Validate the tool exists before calling it
            if step.tool_name not in TOOL_FUNCTIONS:
                result = {"error": f"Unknown tool: {step.tool_name}"}
            else:
                fn     = TOOL_FUNCTIONS[step.tool_name]
                result = await fn(cve_id)

            observations.append({
                "step":      step.step,
                "tool":      step.tool_name,
                "result":    result,
            })
            execution_log.append({
                "step":        step.step,
                "description": step.description,
                "tool":        step.tool_name,
                "result":      result,
                "status":      "error" if "error" in result else "ok",
            })

        elif step.step_type == "synthesise":
            # The synthesis step uses all collected observations to produce
            # the final report. No tool is called here — the LLM synthesises.
            obs_json = json.dumps(observations, indent=2)

            final_response = await client.chat.completions.create(
                model=MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a CVE analyst. Produce a final structured risk report "
                            "based only on the data provided. Do not invent any values."
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            f"CVE under investigation: {cve_id}\n\n"
                            f"Data collected from {len(observations)} steps:\n{obs_json}\n\n"
                            "Produce the final risk report."
                        ),
                    },
                ],
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name":   "PlanExecuteReport",
                        "strict": True,
                        "schema": _strict_schema(PlanExecuteReport),
                    },
                },
                temperature=0.1,
                max_tokens=2048,
            )
            _track(final_response)
            report = PlanExecuteReport.model_validate(
                json.loads(final_response.choices[0].message.content)
            )
            execution_log.append({
                "step":        step.step,
                "description": step.description,
                "tool":        "synthesise",
                "status":      "ok",
            })
            return report, execution_log

    raise RuntimeError("Plan had no synthesise step — cannot produce final report")


# ─── MAIN PIPELINE ────────────────────────────────────────────────────────────

async def analyse_cve(cve_id: str) -> tuple[InvestigationPlan, PlanExecuteReport, list[dict]]:
    """
    Full Plan-and-Execute pipeline.

    Returns:
      plan          — the investigation plan (inspect it to understand WHY these steps)
      report        — the final analysis
      execution_log — step-by-step record of what was executed and what was found
    """
    _reset_usage()
    console.print(f"\n[dim]  Phase 1: Planning investigation of {cve_id}...[/dim]")
    start = time.perf_counter()

    plan = await create_plan(cve_id)
    console.print(f"[dim]  Plan produced: {len(plan.steps)} steps[/dim]")
    for s in plan.steps:
        console.print(f"[dim]    {s.step}. [{s.step_type}] {s.description}[/dim]")

    console.print(f"\n[dim]  Phase 2: Executing plan...[/dim]")
    report, execution_log = await execute_plan(cve_id, plan)

    elapsed = time.perf_counter() - start
    console.print(f"[dim]  Completed in {elapsed:.1f}s[/dim]")

    return plan, report, execution_log


# ─── DISPLAY HELPERS ──────────────────────────────────────────────────────────

SEVERITY_COLOURS = {
    "CRITICAL": "bold red",
    "HIGH":     "red",
    "MEDIUM":   "yellow",
    "LOW":      "green",
}


def display_plan(plan: InvestigationPlan) -> None:
    console.print("\n[bold dim]── Investigation Plan ──────────────────────────────────────────[/bold dim]")
    console.print(f"[dim]Goal: {plan.goal}[/dim]")
    console.print(f"[dim]Planner reasoning: {plan.reasoning}[/dim]\n")

    for step in plan.steps:
        style = "cyan" if step.step_type == "tool_call" else "green"
        label = f"[{style}]{step.step_type}[/{style}]"
        tool  = f"  [dim]→ {step.tool_name}[/dim]" if step.tool_name else ""
        console.print(f"  Step {step.step} {label}{tool}")
        console.print(f"    [dim]{step.description}[/dim]")


def display_execution(log: list[dict]) -> None:
    console.print("\n[bold dim]── Execution Log ───────────────────────────────────────────────[/bold dim]")
    for entry in log:
        status_str = "[green]OK[/green]" if entry["status"] == "ok" else "[red]ERROR[/red]"
        result     = entry.get("result", {})
        if isinstance(result, dict) and "error" not in result:
            preview = result.get("note") or result.get("description", "")
            if preview:
                preview = preview[:100]
            else:
                preview = str(result)[:100]
        elif isinstance(result, dict):
            preview = f"ERROR: {result.get('error')}"
        else:
            preview = "(synthesis step)"

        console.print(Panel(
            f"[dim]{preview}[/dim]",
            title=f"Step {entry['step']} — {entry['tool']}  {status_str}",
            border_style="dim",
            padding=(0, 1),
        ))


def display_report(report: PlanExecuteReport) -> None:
    severity = report.cvss_severity.upper()
    colour   = SEVERITY_COLOURS.get(severity, "white")
    epss_pct = report.epss_score * 100

    kev_str = (
        "[bold red]YES — Actively exploited (CISA KEV)[/bold red]"
        if report.in_cisa_kev else
        "[green]No (not in CISA KEV)[/green]"
    )

    t = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
    t.add_column(style="dim", width=22)
    t.add_column()

    t.add_row("CVE",             f"[bold]{report.cve_id}[/bold]")
    t.add_row("CVSS Score",      f"[{colour}]{report.cvss_score} ({report.cvss_severity})[/{colour}]")
    t.add_row("EPSS Score",      f"{epss_pct:.1f}%  [dim]({report.epss_percentile * 100:.0f}th percentile)[/dim]")
    t.add_row("Active Exploit",  kev_str)
    t.add_row("Patch Available", "[green]Yes[/green]" if report.patch_available else "[red]No[/red]")
    t.add_row("Steps Executed",  str(report.steps_executed))
    t.add_row("Data Sources",    ", ".join(report.data_sources))
    t.add_row("",                "")
    t.add_row("Risk Verdict",    report.risk_verdict)
    t.add_row("",                "")
    t.add_row("Recommended",     report.recommended_action)

    console.print(Panel(
        t,
        title=f"[bold]Plan-and-Execute Report — {report.cve_id}[/bold]",
        border_style=colour.replace("bold ", ""),
        padding=(1, 2),
    ))


# ─── ENTRY POINT ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    cve_id = sys.argv[1] if len(sys.argv) > 1 else "CVE-2021-44228"

    console.print()
    console.print(Text("VIGIL", style="bold cyan") + Text(" — Architecture 2: Plan-and-Execute", style="dim"))
    console.print(f"[dim]Model: {MODEL}  |  CVE: {cve_id}[/dim]")
    console.print(f"[dim]Pattern: Plan (one LLM call) → Execute (one tool call per step)[/dim]")

    plan, report, log = asyncio.run(analyse_cve(cve_id))

    display_plan(plan)
    display_execution(log)
    console.print()
    display_report(report)
    console.print()

    usage = get_usage()
    console.print(
        f"[dim]Tokens: {usage['total_tokens']:,} "
        f"({usage['prompt_tokens']:,} in / {usage['completion_tokens']:,} out)  "
        f"· Cost: ~${usage['estimated_cost_usd']:.4f} USD[/dim]"
    )
    console.print()
