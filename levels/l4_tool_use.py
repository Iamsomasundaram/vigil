"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  VIGIL — Level 4: Tool Use                                                 ║
║                                                                              ║
║  The agent calls real external APIs to ground its analysis in live data.    ║
║  It decides WHICH tools to call and WHEN — we don't hardcode the sequence.  ║
╚══════════════════════════════════════════════════════════════════════════════╝

CONCEPTS COVERED
────────────────
  1. Tool definitions     — describing capabilities the LLM can invoke
  2. Tool calling loop    — the model emits a tool call; we execute it; repeat
  3. Grounding            — replacing model memory with live, verifiable data
  4. ReAct pattern        — Reason → Act → Observe → Reason → Act → ...
  5. Tool result injection — feeding real API responses back into the conversation

WHY TOOL USE?
─────────────
  Levels L0–L3 ask the LLM to rely on its training data:
    "What is CVE-2021-44228?"  → model recites from memory

  Problems with memory-only analysis:
    • Model knowledge has a training cutoff — new CVEs are unknown
    • CVSS scores change as exploitability is reassessed
    • EPSS scores (probability of exploitation in 30 days) update daily
    • Patch availability changes as vendors release fixes

  Tool use solves this: the model can LOOK THINGS UP in real time.
    "What is CVE-2024-XXXX?"  → model calls NVD API → gets live data → analyses it

  This is the difference between a well-read analyst and a connected analyst.

THE TOOLS WE USE
────────────────
  NVD (National Vulnerability Database) — nvd.nist.gov/developers
    Free, no API key required (rate-limited to 5 req/30s without key)
    Returns: description, CVSS scores, affected CPEs, references

  EPSS (Exploit Prediction Scoring System) — first.org/epss
    Probability (0–1) that a CVE will be exploited in the next 30 days
    Updated daily. A CVSS 9.0 with EPSS 0.001 is less urgent than a
    CVSS 6.0 with EPSS 0.85.
    Free, no API key required.

HOW TOOL CALLING WORKS
────────────────────────
  Traditional call:  you decide what to call and when
    step1()  → step2()  → step3()

  Tool calling:      the LLM decides what to call and when
    ┌──────────────────────────────────────────────────────┐
    │  User: "Analyse CVE-2024-12345"                      │
    │                                                      │
    │  LLM: I need the NVD data.                           │
    │       → tool_call: fetch_nvd("CVE-2024-12345")       │
    │                                                      │
    │  [we execute the tool, return the result]            │
    │                                                      │
    │  LLM: I also need the EPSS score.                    │
    │       → tool_call: fetch_epss("CVE-2024-12345")      │
    │                                                      │
    │  [we execute the tool, return the result]            │
    │                                                      │
    │  LLM: Now I have enough data. Here is my analysis.   │
    │       → final text response                          │
    └──────────────────────────────────────────────────────┘

  The model drives the tool calls. You just provide the tools and
  execute whatever it asks for. This is the ReAct pattern:
    Reason  — model decides it needs data
    Act     — model emits a tool_call
    Observe — model receives the tool result
    Reason  — model decides what to do next
    (repeat until the model produces a final response)

THE TOOL CALLING LOOP
──────────────────────
  The loop is the core primitive:

    messages = [system, user]
    while True:
        response = llm(messages, tools=TOOLS)

        if response has tool_calls:
            for each tool_call:
                result = execute_tool(tool_call)
                messages.append(tool_call)         # the model's request
                messages.append(tool_result)       # our execution result
            # loop back — give the model the results
        else:
            # model produced a final response, no more tool calls
            break

  Each iteration adds to the conversation. The model accumulates context
  until it has everything it needs.

GROUNDING VS HALLUCINATION
───────────────────────────
  Without tools (L0–L3), the model may:
    - Invent plausible-sounding CVSS scores
    - Claim a patch exists when it doesn't
    - Miss CVEs published after its training cutoff

  With tools, every fact can be traced to an API call. This is "grounding":
  the model's claims are anchored to verifiable external data.

  In production AI, grounding is not optional. Ungrounded analysis of
  security vulnerabilities can lead to missed patches or false urgency.

RUN THIS FILE
─────────────
  python levels/l4_tool_use.py
  python levels/l4_tool_use.py CVE-2023-44487
  python levels/l4_tool_use.py CVE-2014-0160
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

# Shared HTTP client for all tool calls.
# Using a single httpx.AsyncClient means connections are pooled across tool
# calls within one analysis request — faster than creating a new client each time.
http = httpx.AsyncClient(timeout=15.0)


# ─── SCHEMA HELPERS ───────────────────────────────────────────────────────────
# (Same pattern as L1–L3 — see l1_chain.py for full explanation)

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


# ─── FINAL REPORT SCHEMA ──────────────────────────────────────────────────────
# This is what the model produces AFTER it has finished calling tools.
# Grounded fields reference the real data it fetched, not training memory.

class GroundedAnalysis(_Base):
    """
    Final analysis produced after the agent has fetched live data.

    Every numeric field here comes from a real API call — the model cannot
    invent these values because they were injected into its context as tool
    results. This is the grounding guarantee.
    """
    cve_id:             str
    cvss_score:         float  = Field(description="From NVD API — real current score")
    cvss_severity:      str    = Field(description="Critical / High / Medium / Low")
    epss_score:         float  = Field(ge=0.0, le=1.0, description="Exploitation probability (0–1) from EPSS API")
    epss_percentile:    float  = Field(ge=0.0, le=1.0, description="How this CVE ranks among all CVEs by exploitation likelihood")
    description:        str    = Field(description="Official NVD description")
    patch_available:    bool
    recommended_action: str    = Field(description="What to do, grounded in the live data")
    data_sources:       list[str] = Field(description="Which APIs were actually called")


# ─── TOOL DEFINITIONS ─────────────────────────────────────────────────────────
# Tool definitions tell the LLM what capabilities are available.
# Each definition has:
#   name        — the function the model will call by name
#   description — plain English explanation the model uses to decide WHEN to call it
#   parameters  — JSON schema for what arguments the model must provide
#
# The model reads these at the start of the conversation. When it decides to
# use a tool, it emits a tool_call with the function name and arguments.
# We then execute the real function and return the result.
#
# KEY POINT: the model never executes tools directly. It asks us to execute
# them by emitting structured tool_call messages. We remain in control.

TOOLS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "fetch_nvd_data",
            "description": (
                "Fetches live vulnerability data from the National Vulnerability Database (NVD). "
                "Returns the official description, CVSS scores, severity, and affected products. "
                "Use this first — it provides the authoritative source of truth for any CVE."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "cve_id": {
                        "type": "string",
                        "description": "The CVE identifier, e.g. CVE-2021-44228",
                    }
                },
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
                "Fetches the EPSS (Exploit Prediction Scoring System) score for a CVE. "
                "EPSS gives the probability (0–1) that the CVE will be exploited in the next 30 days, "
                "updated daily by FIRST.org. A high EPSS score means active exploitation is likely "
                "even if the CVSS score is moderate. Always call this after fetch_nvd_data to get "
                "a complete risk picture."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "cve_id": {
                        "type": "string",
                        "description": "The CVE identifier, e.g. CVE-2021-44228",
                    }
                },
                "required": ["cve_id"],
                "additionalProperties": False,
            },
        },
    },
]


# ─── TOOL IMPLEMENTATIONS ─────────────────────────────────────────────────────
# These are the actual functions that run when the model requests a tool call.
# They hit real external APIs and return real data.
#
# The return value must be a string — that's what gets injected back into the
# conversation as the tool result. We use JSON strings for structure.

async def fetch_nvd_data(cve_id: str) -> str:
    """
    Call the NVD REST API v2.0 and return structured vulnerability data.

    NVD API docs: https://nvd.nist.gov/developers/vulnerabilities
    Rate limit: 5 requests per 30 seconds without an API key.
    Returns a JSON string the model can read and reason about.
    """
    url = f"https://services.nvd.nist.gov/rest/json/cves/2.0?cveId={cve_id}"
    try:
        response = await http.get(url)
        response.raise_for_status()
        data = response.json()

        vulns = data.get("vulnerabilities", [])
        if not vulns:
            return json.dumps({"error": f"CVE {cve_id} not found in NVD"})

        cve = vulns[0]["cve"]

        # Extract the English description
        descriptions = cve.get("descriptions", [])
        description  = next(
            (d["value"] for d in descriptions if d["lang"] == "en"),
            "No description available"
        )

        # Extract CVSS score — try v3.1 first, fall back to v3.0, then v2
        metrics     = cve.get("metrics", {})
        cvss_score  = None
        cvss_vector = None
        severity    = None

        for version_key in ("cvssMetricV31", "cvssMetricV30", "cvssMetricV2"):
            if version_key in metrics:
                m           = metrics[version_key][0]["cvssData"]
                cvss_score  = m.get("baseScore")
                cvss_vector = m.get("vectorString")
                severity    = m.get("baseSeverity") or metrics[version_key][0].get("baseSeverity")
                break

        # Extract references (first 3 — enough context without overwhelming the model)
        references = [r["url"] for r in cve.get("references", [])[:3]]

        result = {
            "source":      "NVD",
            "cve_id":      cve_id,
            "published":   cve.get("published", "unknown"),
            "description": description,
            "cvss_score":  cvss_score,
            "cvss_vector": cvss_vector,
            "severity":    severity,
            "references":  references,
        }
        return json.dumps(result)

    except httpx.HTTPStatusError as e:
        return json.dumps({"error": f"NVD API returned {e.response.status_code}"})
    except Exception as e:
        return json.dumps({"error": f"NVD API call failed: {str(e)}"})


async def fetch_epss_score(cve_id: str) -> str:
    """
    Call the EPSS API and return the exploitation probability score.

    EPSS API docs: https://www.first.org/epss/api
    No authentication required. Updated daily.

    The score is a probability from 0 to 1:
      0.001 = 0.1% chance of exploitation in next 30 days (low)
      0.5   = 50% chance (high)
      0.95  = 95% chance (extremely high)

    The percentile tells you how this CVE compares to all others.
    A score of 0.3 at the 95th percentile means only 5% of CVEs are
    more likely to be exploited — context that CVSS alone doesn't give.
    """
    url = f"https://api.first.org/data/v1/epss?cve={cve_id}"
    try:
        response = await http.get(url)
        response.raise_for_status()
        data = response.json()

        items = data.get("data", [])
        if not items:
            return json.dumps({
                "source": "EPSS",
                "cve_id": cve_id,
                "score":  None,
                "note":   "CVE not found in EPSS database — may be too recent or unscored",
            })

        item = items[0]
        return json.dumps({
            "source":     "EPSS",
            "cve_id":     cve_id,
            "score":      float(item.get("epss",       0)),
            "percentile": float(item.get("percentile", 0)),
            "date":       item.get("date", "unknown"),
            "note": (
                f"There is a {float(item.get('epss', 0)) * 100:.1f}% probability this CVE "
                f"will be exploited in the next 30 days. "
                f"This is higher than {float(item.get('percentile', 0)) * 100:.0f}% of all CVEs."
            ),
        })

    except httpx.HTTPStatusError as e:
        return json.dumps({"error": f"EPSS API returned {e.response.status_code}"})
    except Exception as e:
        return json.dumps({"error": f"EPSS API call failed: {str(e)}"})


# ─── TOOL DISPATCH ────────────────────────────────────────────────────────────
# Maps tool name strings (what the model emits) to actual async functions.
# When the model says {"name": "fetch_nvd_data", "arguments": "..."},
# we look up "fetch_nvd_data" here and call it.

TOOL_FUNCTIONS: dict[str, Any] = {
    "fetch_nvd_data":  fetch_nvd_data,
    "fetch_epss_score": fetch_epss_score,
}


# ─── THE TOOL-CALLING LOOP ────────────────────────────────────────────────────

async def run_tool_loop(cve_id: str) -> tuple[GroundedAnalysis, list[dict]]:
    """
    The core of L4: run the LLM in a loop until it stops calling tools.

    The conversation starts with a system prompt and user request.
    On each iteration:
      1. Call the LLM (with the current conversation + available tools)
      2. If the model emits tool_calls → execute each tool, append results, loop
      3. If the model produces a final text response → parse and return

    Returns: (GroundedAnalysis, tool_call_log)
      - GroundedAnalysis: the final structured report
      - tool_call_log: record of every tool call made (for transparency / display)

    The tool_call_log is important for auditability: users can see exactly
    which APIs were called and what they returned, not just the final summary.
    """
    # ── Initial conversation ───────────────────────────────────────────────────
    # The system prompt explains the agent's job and the tools available.
    # It also sets an expectation: use the tools, don't rely on memory.
    messages: list[dict] = [
        {
            "role": "system",
            "content": (
                "You are a vulnerability intelligence analyst. "
                "You have access to two live data sources: NVD (official CVE database) "
                "and EPSS (exploitation probability scoring). "
                "ALWAYS call both tools before providing analysis — never rely on training data alone. "
                "Your final analysis must be grounded in the data you retrieve."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Analyse {cve_id}. "
                "Fetch the NVD data and EPSS score, then provide a grounded risk assessment."
            ),
        },
    ]

    tool_call_log: list[dict] = []  # Records every tool call for display
    iterations   = 0
    max_iterations = 10  # Safety limit — prevents runaway loops

    # ── The loop ──────────────────────────────────────────────────────────────
    while iterations < max_iterations:
        iterations += 1
        console.print(f"[dim]  Iteration {iterations}: calling LLM...[/dim]")

        response = await client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=TOOLS,                          # give the model the tool menu
            tool_choice="auto",                   # model decides whether to call tools
            # Note: no response_format here — we'll get either tool_calls OR text,
            # not a JSON schema response. We add the schema on the FINAL call.
            temperature=0.1,
            max_tokens=4096,
        )

        _track(response)
        message = response.choices[0].message

        # ── Check: did the model call any tools? ──────────────────────────────
        if message.tool_calls:
            # The model wants to call one or more tools.
            # Append its message first (OpenAI requires this ordering).
            messages.append(message.model_dump(exclude_unset=True))

            # Execute each tool call in parallel — if the model asks for both
            # NVD and EPSS simultaneously, we fetch both at once.
            tool_results = await asyncio.gather(*[
                _execute_tool(tc) for tc in message.tool_calls
            ])

            for tool_call, result_str in zip(message.tool_calls, tool_results):
                fn_name = tool_call.function.name
                args    = json.loads(tool_call.function.arguments)

                console.print(f"[dim]    → tool: {fn_name}({', '.join(f'{k}={v}' for k, v in args.items())})[/dim]")

                # Log it for the display layer
                tool_call_log.append({
                    "tool":      fn_name,
                    "arguments": args,
                    "result":    json.loads(result_str) if result_str.startswith("{") else result_str,
                })

                # Inject the result back into the conversation.
                # The model will read this on the next iteration.
                messages.append({
                    "role":         "tool",
                    "tool_call_id": tool_call.id,
                    "content":      result_str,
                })

            # Loop back — model now has tool results and will decide what to do next
            continue

        # ── No more tool calls: model produced a final response ───────────────
        # At this point the model has all the data it needs.
        # We make one more structured call to get the final GroundedAnalysis.
        console.print(f"[dim]  Tools complete. Requesting structured final report...[/dim]")

        final_response = await client.chat.completions.create(
            model=MODEL,
            messages=messages + [
                {
                    "role": "user",
                    "content": (
                        "Based on the live data you just retrieved, produce the final structured analysis. "
                        "Use only facts from the tool results — do not add information from training memory."
                    ),
                }
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name":   "GroundedAnalysis",
                    "strict": True,
                    "schema": _strict_schema(GroundedAnalysis),
                },
            },
            temperature=0.1,
            max_tokens=2048,
        )

        _track(final_response)
        analysis = GroundedAnalysis.model_validate(
            json.loads(final_response.choices[0].message.content)
        )
        return analysis, tool_call_log

    # If we hit max_iterations without a final response, something went wrong
    raise RuntimeError(f"Tool loop exceeded {max_iterations} iterations — agent may be stuck")


async def _execute_tool(tool_call) -> str:
    """
    Execute a single tool call and return its result as a string.

    This is the boundary between the LLM world and the real world:
    the model asks → we execute → we return the result.
    """
    fn_name   = tool_call.function.name
    arguments = json.loads(tool_call.function.arguments)

    fn = TOOL_FUNCTIONS.get(fn_name)
    if fn is None:
        # If the model hallucinates a tool name, return a clear error.
        # The model will read this and understand the tool doesn't exist.
        return json.dumps({"error": f"Unknown tool: {fn_name}"})

    return await fn(**arguments)


# ─── MAIN PIPELINE ────────────────────────────────────────────────────────────

async def analyse_cve(cve_id: str) -> tuple[GroundedAnalysis, list[dict]]:
    """
    Full L4 pipeline: tool-calling loop → grounded structured report.

    Unlike L1–L3, the agent drives the workflow. We just provide tools
    and execute what it asks for.
    """
    _reset_usage()
    console.print(f"\n[dim]  Starting tool-use loop for {cve_id}...[/dim]")
    start = time.perf_counter()

    analysis, tool_log = await run_tool_loop(cve_id)

    elapsed = time.perf_counter() - start
    console.print(f"[dim]  Completed in {elapsed:.1f}s ({len(tool_log)} tool calls)[/dim]")

    return analysis, tool_log


# ─── DISPLAY HELPERS ──────────────────────────────────────────────────────────

SEVERITY_COLOURS = {
    "CRITICAL": "bold red",
    "HIGH":     "red",
    "MEDIUM":   "yellow",
    "LOW":      "green",
}


def display_tool_log(tool_log: list[dict]) -> None:
    """
    Show which tools were called and what they returned.

    Transparency about tool calls is important: learners can see exactly
    what the agent fetched, not just the final polished summary.
    In production, this becomes your audit trail.
    """
    for i, entry in enumerate(tool_log, 1):
        result = entry["result"]
        # Show a compact preview of the tool result, not the full JSON
        if isinstance(result, dict) and "error" not in result:
            if entry["tool"] == "fetch_nvd_data":
                preview = f"CVSS {result.get('cvss_score')} ({result.get('severity')}) — {result.get('description', '')[:80]}..."
            elif entry["tool"] == "fetch_epss_score":
                preview = result.get("note", str(result))
            else:
                preview = str(result)[:120]
        else:
            preview = result.get("error", str(result)) if isinstance(result, dict) else str(result)

        console.print(Panel(
            f"[dim]{preview}[/dim]",
            title=f"[bold]Tool {i}: {entry['tool']}[/bold]  [dim]{entry['arguments']}[/dim]",
            border_style="dim",
            padding=(0, 1),
        ))


def display_analysis(analysis: GroundedAnalysis) -> None:
    severity = analysis.cvss_severity.upper()
    colour   = SEVERITY_COLOURS.get(severity, "white")

    # EPSS score visual indicator
    epss_pct = analysis.epss_score * 100
    if epss_pct >= 50:
        epss_colour = "bold red"
    elif epss_pct >= 10:
        epss_colour = "yellow"
    else:
        epss_colour = "green"

    t = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
    t.add_column(style="dim", width=22)
    t.add_column()

    t.add_row("CVE",          f"[bold]{analysis.cve_id}[/bold]")
    t.add_row("CVSS Score",   f"[{colour}]{analysis.cvss_score} ({analysis.cvss_severity})[/{colour}]")
    t.add_row("EPSS Score",   (
        f"[{epss_colour}]{analysis.epss_score:.4f}[/{epss_colour}]  "
        f"[dim]({epss_pct:.1f}% exploitation probability, "
        f"{analysis.epss_percentile*100:.0f}th percentile)[/dim]"
    ))
    t.add_row("Patch",        "[green]Available[/green]" if analysis.patch_available else "[red]Not yet available[/red]")
    t.add_row("Data sources", ", ".join(analysis.data_sources))
    t.add_row("",             "")
    t.add_row("Description",  analysis.description[:120] + ("..." if len(analysis.description) > 120 else ""))
    t.add_row("",             "")
    t.add_row("Recommended",  analysis.recommended_action)

    console.print(Panel(
        t,
        title=f"[bold]Grounded Analysis — {analysis.cve_id}[/bold]",
        border_style=colour.replace("bold ", ""),
        padding=(1, 2),
    ))


# ─── ENTRY POINT ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    cve_id = sys.argv[1] if len(sys.argv) > 1 else "CVE-2021-44228"

    console.print()
    console.print(Text("VIGIL", style="bold cyan") + Text(" — Level 4: Tool Use", style="dim"))
    console.print(f"[dim]Model: {MODEL}  |  CVE: {cve_id}[/dim]")
    console.print(f"[dim]Tools: NVD API + EPSS API (live data)[/dim]")

    analysis, tool_log = asyncio.run(analyse_cve(cve_id))

    console.print()
    console.print("[bold dim]── Tool Calls ─────────────────────────────────────────────[/bold dim]")
    display_tool_log(tool_log)
    console.print()
    display_analysis(analysis)
    console.print()
