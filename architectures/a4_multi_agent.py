"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  VIGIL — Architecture 4: Multi-Agent                                       ║
║                                                                              ║
║  An orchestrator decomposes the task and dispatches it to specialist        ║
║  agents. Each agent has a focused role, its own tools, and reports back.    ║
╚══════════════════════════════════════════════════════════════════════════════╝

WHAT IS MULTI-AGENT?
─────────────────────
  Multi-Agent systems use multiple LLM instances — each with a distinct role,
  identity, and toolset — coordinated by an orchestrator.

  The structure:
    ┌──────────────────────────────────────────────────────────────────────┐
    │               ORCHESTRATOR                                           │
    │   "Here is the task. Agent A, do X. Agent B, do Y. Agent C, do Z."  │
    │   Collects results and synthesises the final output.                │
    └──────────┬─────────────────┬──────────────────┬───────────────────--┘
               │                 │                  │
    ┌──────────▼──────┐ ┌────────▼───────┐ ┌────────▼───────────┐
    │  Threat Intel   │ │  Impact        │ │  Patch & Remediation│
    │  Agent          │ │  Assessment    │ │  Agent              │
    │                 │ │  Agent         │ │                     │
    │  Tools: NVD,    │ │  Tools: EPSS,  │ │  Tools: CISA KEV,   │
    │  CISA KEV       │ │  NVD           │ │  NVD                │
    └─────────────────┘ └────────────────┘ └─────────────────────┘

WHY MULTI-AGENT?
─────────────────
  Single agents trying to do everything encounter several problems:

  1. Context window pressure — a single agent doing 10 tasks accumulates a
     large context that slows it down and can cause earlier instructions to
     be forgotten.

  2. Role confusion — an agent asked to be both a threat analyst AND a
     remediation planner may blend the two perspectives inconsistently.

  3. Parallelism — if the tasks are independent, running them simultaneously
     is faster. Multi-agent fan-out is the natural parallel execution model.

  4. Specialisation — a threat intel agent can be given a very focused system
     prompt that makes it excellent at ONE thing, rather than mediocre at many.

  Multi-Agent is the architecture pattern behind products like AutoGPT, CrewAI,
  LangGraph multi-agent workflows, and most enterprise agentic systems.

THE AGENTS IN THIS FILE
────────────────────────
  Orchestrator — decomposes the CVE investigation into three parallel tasks
                 and synthesises the agent reports into a final verdict.
                 Does NOT call tools itself.

  Threat Intel Agent — answers: "What is this vulnerability? Is it being
                       actively exploited?"
                       Tools: NVD (description, CVSS), CISA KEV (active exploit)

  Impact Assessment Agent — answers: "How likely is exploitation and who is
                             at risk?"
                             Tools: EPSS (probability), NVD (affected products)

  Patch & Remediation Agent — answers: "What should we do? Is a fix available?
                               How urgent is patching?"
                               Tools: NVD (patch references), CISA KEV (deadline)

COORDINATION PATTERN: PARALLEL DISPATCH
─────────────────────────────────────────
  All three specialist agents run concurrently via asyncio.gather().
  Each has its own system prompt, tools, and conversation thread.
  None of them can see the other agents' work.
  The orchestrator receives all three reports and synthesises the final output.

  This is the "fan-out / fan-in" pattern:
    orchestrator → [agent_a, agent_b, agent_c] (parallel)
    orchestrator ← [report_a, report_b, report_c] (aggregate)
    orchestrator → final_synthesis

HOW THIS DIFFERS FROM L2 (Parallel Fan-out)
─────────────────────────────────────────────
  L2 (levels/l2_parallel.py):
    • Fixed set of agents, fixed roles, hardcoded in the level
    • Agents don't use tools — they reason from training data
    • Moderator synthesises; no orchestrator decides dispatch

  A4 Multi-Agent:
    • Orchestrator dynamically describes each agent's specific subtask
    • Each agent has its own real tools for live data
    • Agents report back with structured outputs the orchestrator interprets
    • The pattern is extensible: add a "Legal & Compliance" agent, etc.

RUN THIS FILE
─────────────
  python architectures/a4_multi_agent.py
  python architectures/a4_multi_agent.py CVE-2021-44228
  python architectures/a4_multi_agent.py CVE-2023-44487
"""

import asyncio
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv
from openai import AsyncOpenAI
from pydantic import BaseModel, ConfigDict, Field
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box
from vigil.models import AgentMessage, Consensus

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


# ─── AGENT REPORT SCHEMAS ─────────────────────────────────────────────────────

class ThreatIntelReport(_Base):
    """
    Output of the Threat Intel Agent.
    Focuses on: what is this vulnerability and is it actively exploited?
    """
    agent:              str   = Field(description="Always 'threat_intel'")
    cve_id:             str
    description:        str   = Field(description="What the vulnerability is and how it works")
    cvss_score:         float
    cvss_severity:      str
    actively_exploited: bool  = Field(description="Is this in CISA KEV?")
    kev_date_added:     str   = Field(description="Date added to CISA KEV, or 'N/A'")
    threat_summary:     str   = Field(description="2-sentence threat intelligence summary")


class ImpactReport(_Base):
    """
    Output of the Impact Assessment Agent.
    Focuses on: how likely is exploitation and what is the blast radius?
    """
    agent:               str   = Field(description="Always 'impact_assessment'")
    cve_id:              str
    epss_score:          float = Field(ge=0.0, le=1.0)
    epss_percentile:     float = Field(ge=0.0, le=1.0)
    exploitation_likely: bool  = Field(description="Is epss_score > 0.10?")
    affected_scope:      str   = Field(description="Who is affected? (from NVD CPE data or description)")
    impact_summary:      str   = Field(description="2-sentence impact assessment")


class RemediationReport(_Base):
    """
    Output of the Patch & Remediation Agent.
    Focuses on: what should we do and how urgently?
    """
    agent:              str   = Field(description="Always 'patch_remediation'")
    cve_id:             str
    patch_available:    bool
    urgency:            str   = Field(description="immediate / high / medium / low")
    kev_due_date:       str   = Field(description="CISA KEV remediation deadline, or 'N/A'")
    required_action:    str   = Field(description="Specific remediation steps")
    remediation_summary: str  = Field(description="2-sentence remediation guidance")


class MultiAgentReport(_Base):
    """
    Final report synthesised by the orchestrator from all three agent reports.
    """
    cve_id:              str
    cvss_score:          float
    cvss_severity:       str
    epss_score:          float         = Field(ge=0.0, le=1.0)
    epss_percentile:     float         = Field(ge=0.0, le=1.0)
    actively_exploited:  bool
    patch_available:     bool
    overall_urgency:     str           = Field(description="immediate / high / medium / low")
    risk_verdict:        str           = Field(description="Combined risk narrative from all three agents")
    recommended_action:  str           = Field(description="Synthesised recommendation")
    agents_consulted:    list[str]     = Field(description="Which agents contributed to this report")


# ─── TOOL IMPLEMENTATIONS ─────────────────────────────────────────────────────
# Each agent gets access to a subset of tools relevant to its role.

async def fetch_nvd_data(cve_id: str) -> dict:
    url = f"https://services.nvd.nist.gov/rest/json/cves/2.0?cveId={cve_id}"
    try:
        r     = await http.get(url)
        r.raise_for_status()
        vulns = r.json().get("vulnerabilities", [])
        if not vulns:
            return {"error": f"{cve_id} not found in NVD"}
        cve   = vulns[0]["cve"]
        desc  = next((d["value"] for d in cve.get("descriptions", []) if d["lang"] == "en"), "No description")
        metrics    = cve.get("metrics", {})
        cvss_score = severity = None
        for key in ("cvssMetricV31", "cvssMetricV30", "cvssMetricV2"):
            if key in metrics:
                m          = metrics[key][0]["cvssData"]
                cvss_score = m.get("baseScore")
                severity   = m.get("baseSeverity") or metrics[key][0].get("baseSeverity")
                break
        refs = [r["url"] for r in cve.get("references", [])[:3]]
        return {
            "source": "NVD", "cve_id": cve_id, "description": desc,
            "cvss_score": cvss_score, "severity": severity, "references": refs,
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
            return {"source": "EPSS", "score": None, "note": "Not scored"}
        item  = items[0]
        score = float(item.get("epss", 0))
        pct   = float(item.get("percentile", 0))
        return {
            "source": "EPSS", "cve_id": cve_id, "score": score, "percentile": pct,
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
                "source": "CISA KEV", "in_kev": True,
                "date_added": match.get("dateAdded"),
                "due_date":   match.get("dueDate"),
                "required_action": match.get("requiredAction"),
            }
        return {"source": "CISA KEV", "in_kev": False}
    except Exception as e:
        return {"error": str(e)}


# ─── TOOL MENUS PER AGENT ─────────────────────────────────────────────────────
# Each agent is given only the tools relevant to its specialisation.
# This keeps the agent focused and reduces hallucination of irrelevant tools.

THREAT_INTEL_TOOLS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name":        "fetch_nvd_data",
            "description": "Get CVE description, CVSS score and severity from NVD.",
            "parameters": {
                "type": "object",
                "properties": {"cve_id": {"type": "string"}},
                "required": ["cve_id"], "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name":        "check_cisa_kev",
            "description": "Check if this CVE is in CISA's Known Exploited Vulnerabilities catalog.",
            "parameters": {
                "type": "object",
                "properties": {"cve_id": {"type": "string"}},
                "required": ["cve_id"], "additionalProperties": False,
            },
        },
    },
]

IMPACT_TOOLS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name":        "fetch_epss_score",
            "description": "Get exploitation probability (0–1, updated daily) from EPSS.",
            "parameters": {
                "type": "object",
                "properties": {"cve_id": {"type": "string"}},
                "required": ["cve_id"], "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name":        "fetch_nvd_data",
            "description": "Get CVE description and affected product scope from NVD.",
            "parameters": {
                "type": "object",
                "properties": {"cve_id": {"type": "string"}},
                "required": ["cve_id"], "additionalProperties": False,
            },
        },
    },
]

REMEDIATION_TOOLS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name":        "fetch_nvd_data",
            "description": "Get NVD references (patch links, advisories) and description.",
            "parameters": {
                "type": "object",
                "properties": {"cve_id": {"type": "string"}},
                "required": ["cve_id"], "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name":        "check_cisa_kev",
            "description": "Check CISA KEV for mandatory remediation deadline and required action.",
            "parameters": {
                "type": "object",
                "properties": {"cve_id": {"type": "string"}},
                "required": ["cve_id"], "additionalProperties": False,
            },
        },
    },
]

ALL_TOOL_FUNCTIONS: dict[str, Any] = {
    "fetch_nvd_data":   fetch_nvd_data,
    "fetch_epss_score": fetch_epss_score,
    "check_cisa_kev":   check_cisa_kev,
}


# ─── GENERIC TOOL-CALLING LOOP ────────────────────────────────────────────────

async def run_agent_with_tools(
    agent_name: str,
    system_prompt: str,
    user_message: str,
    tools: list[dict],
    output_schema: type,
) -> tuple[Any, list[dict]]:
    """
    Run a single specialist agent through its tool-calling loop.

    Each specialist agent is independent: its own messages list, its own
    tools, its own conversation thread. Agents cannot see each other.

    Returns: (structured_report, tool_call_log)
    """
    messages: list[dict] = [
        {"role": "system", "content": system_prompt},
        {"role": "user",   "content": user_message},
    ]
    tool_log       = []
    max_iterations = 8

    for _ in range(max_iterations):
        response = await client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=tools,
            tool_choice="auto",
            temperature=0.1,
            max_tokens=2048,
        )
        _track(response)
        message = response.choices[0].message

        if message.tool_calls:
            messages.append(message.model_dump(exclude_unset=True))

            for tc in message.tool_calls:
                fn_name   = tc.function.name
                args      = json.loads(tc.function.arguments)
                fn        = ALL_TOOL_FUNCTIONS.get(fn_name)
                result    = await fn(**args) if fn else {"error": f"Unknown tool: {fn_name}"}
                result_str = json.dumps(result)

                console.print(f"[dim]    [{agent_name}] → {fn_name}({args})[/dim]")
                tool_log.append({"agent": agent_name, "tool": fn_name, "arguments": args, "result": result})

                messages.append({
                    "role":         "tool",
                    "tool_call_id": tc.id,
                    "content":      result_str,
                })
            continue

        # No more tool calls — produce structured report
        final = await client.chat.completions.create(
            model=MODEL,
            messages=messages + [
                {"role": "user", "content": "Produce your final structured report now."}
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name":   output_schema.__name__,
                    "strict": True,
                    "schema": _strict_schema(output_schema),
                },
            },
            temperature=0.1,
            max_tokens=1024,
        )
        _track(final)
        report = output_schema.model_validate(json.loads(final.choices[0].message.content))
        return report, tool_log

    raise RuntimeError(f"Agent {agent_name} exceeded max iterations")


# ─── THE THREE SPECIALIST AGENTS ──────────────────────────────────────────────

async def run_threat_intel_agent(cve_id: str) -> tuple[ThreatIntelReport, list[dict]]:
    return await run_agent_with_tools(
        agent_name="threat_intel",
        system_prompt=(
            "You are a threat intelligence analyst. Your ONLY focus is: "
            "what is this vulnerability, how does it work, and is it being actively exploited right now? "
            "Use fetch_nvd_data for the official description and severity. "
            "Use check_cisa_kev to determine if CISA has confirmed active exploitation. "
            "Do not speculate about impact or remediation — that is handled by other agents."
        ),
        user_message=f"Provide threat intelligence for {cve_id}.",
        tools=THREAT_INTEL_TOOLS,
        output_schema=ThreatIntelReport,
    )


async def run_impact_agent(cve_id: str) -> tuple[ImpactReport, list[dict]]:
    return await run_agent_with_tools(
        agent_name="impact_assessment",
        system_prompt=(
            "You are an impact assessment analyst. Your ONLY focus is: "
            "how likely is this CVE to be exploited, and what is the scope of affected systems? "
            "Use fetch_epss_score for exploitation probability. "
            "Use fetch_nvd_data to understand what products and versions are affected. "
            "Do not provide remediation guidance — that is handled by another agent."
        ),
        user_message=f"Assess the exploitation likelihood and impact scope for {cve_id}.",
        tools=IMPACT_TOOLS,
        output_schema=ImpactReport,
    )


async def run_remediation_agent(cve_id: str) -> tuple[RemediationReport, list[dict]]:
    return await run_agent_with_tools(
        agent_name="patch_remediation",
        system_prompt=(
            "You are a patch and remediation specialist. Your ONLY focus is: "
            "is a patch available, how urgently should teams act, and what exactly should they do? "
            "Use fetch_nvd_data for NVD references and patch advisories. "
            "Use check_cisa_kev for mandatory remediation deadlines (federal agencies). "
            "Be specific: 'Apply vendor patch' is not actionable. 'Apply Apache log4j 2.17.1 or later' is."
        ),
        user_message=f"Provide patch and remediation guidance for {cve_id}.",
        tools=REMEDIATION_TOOLS,
        output_schema=RemediationReport,
    )


# ─── ORCHESTRATOR ─────────────────────────────────────────────────────────────

async def synthesise_reports(
    cve_id: str,
    threat: ThreatIntelReport,
    impact: ImpactReport,
    remediation: RemediationReport,
) -> MultiAgentReport:
    """
    The orchestrator synthesises all three agent reports into a final verdict.

    The orchestrator sees all three reports and produces a combined assessment
    that weighs the threat intel, impact, and remediation guidance together.
    It does NOT call any tools — it works only from agent reports.
    """
    combined = {
        "threat_intel":      threat.model_dump(),
        "impact_assessment": impact.model_dump(),
        "patch_remediation": remediation.model_dump(),
    }

    response = await client.chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a senior security orchestrator. Three specialist agents have investigated "
                    f"{cve_id} from different angles. Your job is to synthesise their reports into a "
                    "single coherent final assessment. Weigh all three perspectives. "
                    "The overall_urgency must reflect CVSS + EPSS + active exploitation combined."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Synthesise these agent reports for {cve_id}:\n\n"
                    f"{json.dumps(combined, indent=2)}"
                ),
            },
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name":   "MultiAgentReport",
                "strict": True,
                "schema": _strict_schema(MultiAgentReport),
            },
        },
        temperature=0.1,
        max_tokens=2048,
    )
    _track(response)
    return MultiAgentReport.model_validate(json.loads(response.choices[0].message.content))


# ─── MAIN PIPELINE ────────────────────────────────────────────────────────────

async def analyse_cve(
    cve_id: str,
) -> tuple[ThreatIntelReport, ImpactReport, RemediationReport, MultiAgentReport, list[dict]]:
    """
    Full Multi-Agent pipeline:
      1. Dispatch three specialist agents in parallel
      2. Collect their reports
      3. Orchestrator synthesises the final assessment

    The three agents run concurrently — the total time is roughly max(agent_times)
    rather than sum(agent_times).
    """
    _reset_usage()
    console.print(f"\n[dim]  Dispatching three specialist agents for {cve_id}...[/dim]")
    start = time.perf_counter()

    # ── Fan-out: all three agents run concurrently ─────────────────────────────
    (threat, threat_log), (impact, impact_log), (remediation, remediation_log) = (
        await asyncio.gather(
            run_threat_intel_agent(cve_id),
            run_impact_agent(cve_id),
            run_remediation_agent(cve_id),
        )
    )

    console.print(f"[dim]  All agents complete. Orchestrator synthesising...[/dim]")

    # ── Fan-in: orchestrator synthesises ──────────────────────────────────────
    final = await synthesise_reports(cve_id, threat, impact, remediation)

    elapsed   = time.perf_counter() - start
    all_tools = threat_log + impact_log + remediation_log
    console.print(f"[dim]  Completed in {elapsed:.1f}s ({len(all_tools)} total tool calls across 3 agents)[/dim]")

    return threat, impact, remediation, final, all_tools


async def collaborate(
    cve_id: str,
    mode: str = "handoff",
    rounds: int = 2,
) -> Consensus:
    threat, impact, remediation, final, _tool_log = await analyse_cve(cve_id)
    transcript: list[AgentMessage] = []

    if mode == "handoff":
        transcript.append(
            AgentMessage(
                sender="threat_intel",
                recipient="impact_assessment",
                round=1,
                content=threat.threat_summary,
            )
        )
        transcript.append(
            AgentMessage(
                sender="impact_assessment",
                recipient="patch_remediation",
                round=1,
                content=impact.impact_summary,
            )
        )
        transcript.append(
            AgentMessage(
                sender="patch_remediation",
                recipient="orchestrator",
                round=1,
                content=remediation.remediation_summary,
            )
        )
    elif mode == "debate":
        for r in range(1, max(1, rounds) + 1):
            transcript.append(
                AgentMessage(
                    sender="threat_intel",
                    recipient="patch_remediation",
                    round=r,
                    content=f"Round {r}: Active exploit={threat.actively_exploited}. Prioritize speed.",
                )
            )
            transcript.append(
                AgentMessage(
                    sender="patch_remediation",
                    recipient="threat_intel",
                    round=r,
                    content=f"Round {r}: Patch available={remediation.patch_available}. Balance urgency and safety.",
                )
            )
    elif mode == "blackboard":
        transcript.append(
            AgentMessage(
                sender="threat_intel",
                recipient="blackboard",
                round=1,
                content=f"CVSS {threat.cvss_score} ({threat.cvss_severity}), exploited={threat.actively_exploited}",
            )
        )
        transcript.append(
            AgentMessage(
                sender="impact_assessment",
                recipient="blackboard",
                round=1,
                content=f"EPSS {impact.epss_score:.3f}, likely={impact.exploitation_likely}",
            )
        )
        transcript.append(
            AgentMessage(
                sender="patch_remediation",
                recipient="blackboard",
                round=1,
                content=f"urgency={remediation.urgency}, patch_available={remediation.patch_available}",
            )
        )
    else:
        raise ValueError(f"Unknown collaboration mode: {mode}")

    disagreement = bool(threat.actively_exploited and remediation.urgency.lower() in {"medium", "low"})
    return Consensus(
        mode=mode,
        transcript=transcript,
        rounds_used=max(1, rounds if mode == "debate" else 1),
        final_verdict=final.risk_verdict,
        disagreement_noted=disagreement,
    )


# ─── DISPLAY HELPERS ──────────────────────────────────────────────────────────

SEVERITY_COLOURS = {
    "CRITICAL": "bold red",
    "HIGH":     "red",
    "MEDIUM":   "yellow",
    "LOW":      "green",
}

URGENCY_COLOURS = {
    "immediate": "bold red",
    "high":      "red",
    "medium":    "yellow",
    "low":       "green",
}


def display_agent_reports(
    threat: ThreatIntelReport,
    impact: ImpactReport,
    remediation: RemediationReport,
) -> None:
    console.print("\n[bold dim]── Agent Reports ───────────────────────────────────────────────[/bold dim]")

    console.print(Panel(
        f"[bold]CVSS:[/bold] {threat.cvss_score} ({threat.cvss_severity})\n"
        f"[bold]Active exploit:[/bold] {'[red]YES[/red]' if threat.actively_exploited else '[green]No[/green]'}"
        + (f"  (KEV added: {threat.kev_date_added})" if threat.actively_exploited else "") + "\n\n"
        f"[dim]{threat.threat_summary}[/dim]",
        title="[bold cyan]Threat Intel Agent[/bold cyan]",
        border_style="cyan", padding=(0, 1),
    ))

    console.print(Panel(
        f"[bold]EPSS:[/bold] {impact.epss_score * 100:.1f}%  "
        f"[dim]({impact.epss_percentile * 100:.0f}th percentile)[/dim]\n"
        f"[bold]Exploitation likely:[/bold] {'[red]YES[/red]' if impact.exploitation_likely else '[green]No[/green]'}\n"
        f"[bold]Scope:[/bold] [dim]{impact.affected_scope[:100]}[/dim]\n\n"
        f"[dim]{impact.impact_summary}[/dim]",
        title="[bold yellow]Impact Assessment Agent[/bold yellow]",
        border_style="yellow", padding=(0, 1),
    ))

    urgency_colour = URGENCY_COLOURS.get(remediation.urgency.lower(), "white")
    console.print(Panel(
        f"[bold]Patch available:[/bold] {'[green]Yes[/green]' if remediation.patch_available else '[red]No[/red]'}\n"
        f"[bold]Urgency:[/bold] [{urgency_colour}]{remediation.urgency}[/{urgency_colour}]\n"
        + (f"[bold]KEV deadline:[/bold] {remediation.kev_due_date}\n" if remediation.kev_due_date != "N/A" else "")
        + f"[bold]Action:[/bold] [dim]{remediation.required_action}[/dim]\n\n"
        f"[dim]{remediation.remediation_summary}[/dim]",
        title="[bold green]Patch & Remediation Agent[/bold green]",
        border_style="green", padding=(0, 1),
    ))


def display_final(report: MultiAgentReport) -> None:
    severity = report.cvss_severity.upper()
    sev_col  = SEVERITY_COLOURS.get(severity, "white")
    urg_col  = URGENCY_COLOURS.get(report.overall_urgency.lower(), "white")
    epss_pct = report.epss_score * 100

    t = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
    t.add_column(style="dim", width=22)
    t.add_column()

    t.add_row("CVE",              f"[bold]{report.cve_id}[/bold]")
    t.add_row("CVSS Score",       f"[{sev_col}]{report.cvss_score} ({report.cvss_severity})[/{sev_col}]")
    t.add_row("EPSS Score",       f"{epss_pct:.1f}%  [dim]({report.epss_percentile * 100:.0f}th percentile)[/dim]")
    t.add_row("Active Exploit",   "[bold red]YES (CISA KEV)[/bold red]" if report.actively_exploited else "[green]No[/green]")
    t.add_row("Patch Available",  "[green]Yes[/green]" if report.patch_available else "[red]No[/red]")
    t.add_row("Overall Urgency",  f"[{urg_col}]{report.overall_urgency}[/{urg_col}]")
    t.add_row("Agents Consulted", ", ".join(report.agents_consulted))
    t.add_row("",                 "")
    t.add_row("Risk Verdict",     report.risk_verdict)
    t.add_row("",                 "")
    t.add_row("Recommended",      report.recommended_action)

    console.print(Panel(
        t,
        title=f"[bold]Orchestrator — Final Synthesis — {report.cve_id}[/bold]",
        border_style=sev_col.replace("bold ", ""),
        padding=(1, 2),
    ))


# ─── ENTRY POINT ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    cve_id = sys.argv[1] if len(sys.argv) > 1 else "CVE-2021-44228"

    console.print()
    console.print(Text("VIGIL", style="bold cyan") + Text(" — Architecture 4: Multi-Agent", style="dim"))
    console.print(f"[dim]Model: {MODEL}  |  CVE: {cve_id}[/dim]")
    console.print(f"[dim]Pattern: Orchestrator → [ThreatIntel ‖ Impact ‖ Remediation] → Synthesise[/dim]")

    threat, impact, remediation, final, tool_log = asyncio.run(analyse_cve(cve_id))

    display_agent_reports(threat, impact, remediation)
    console.print()
    display_final(final)
    console.print()

    usage = get_usage()
    console.print(
        f"[dim]Tokens: {usage['total_tokens']:,} "
        f"({usage['prompt_tokens']:,} in / {usage['completion_tokens']:,} out)  "
        f"· Cost: ~${usage['estimated_cost_usd']:.4f} USD[/dim]"
    )
    console.print()
