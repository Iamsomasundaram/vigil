"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  VIGIL — Architecture 3: Reflection / Self-Critique                        ║
║                                                                              ║
║  The agent produces an initial assessment, then critiques its own work,     ║
║  then produces an improved final report — a deliberate quality loop.        ║
╚══════════════════════════════════════════════════════════════════════════════╝

WHAT IS REFLECTION?
────────────────────
  Reflection is the pattern where an agent evaluates and improves its own
  output before returning it to the user.

  The cycle:
    ┌──────────────────────────────────────────────────────────────────────┐
    │  DRAFT     — Produce an initial assessment based on available data   │
    │  CRITIQUE  — Identify weaknesses, gaps, errors, and missing context  │
    │  REVISE    — Produce an improved assessment addressing the critique   │
    └──────────────────────────────────────────────────────────────────────┘

  This mirrors how skilled analysts work: first draft → peer review → revision.
  The "peer reviewer" here is the same model, but given an adversarial role.

WHY DOES REFLECTION IMPROVE QUALITY?
──────────────────────────────────────
  LLMs tend to produce fluent, confident-sounding first drafts — even when
  those drafts contain gaps, overconfident claims, or missed nuance.

  Reflection works because:
    1. Switching roles forces a different perspective. The same model that
       wrote "patch immediately" may, in reviewer mode, note "we don't yet
       know if a patch exists."

    2. Critique prompts are adversarial by design — the model is asked to
       FIND problems, not just evaluate neutrally. This surfaces issues that
       a neutral re-read would miss.

    3. The reviser has the original draft AND the critique, making it easier
       to produce a targeted improvement rather than rewriting from scratch.

HOW REFLECTION DIFFERS FROM OTHER ARCHITECTURES
─────────────────────────────────────────────────
  vs. ReAct (A1):
    ReAct focuses on INFORMATION gathering (which tools to call, in what
    order). Reflection focuses on OUTPUT QUALITY (is the report accurate,
    complete, and appropriately hedged?).

  vs. Plan-and-Execute (A2):
    Plan-and-Execute is about structuring ACTIONS before taking them.
    Reflection is about improving OUTPUTS after producing them.

  They can be combined: ReAct + Reflection means gathering data with explicit
  reasoning AND then critiquing the resulting report before returning it.

THE THREE AGENTS IN THIS FILE
───────────────────────────────
  1. Researcher — fetches live data (NVD + EPSS + CISA KEV) and writes
                  an initial CVE risk assessment. Uses the same tools as A1/A2.

  2. Critic     — given the draft assessment, identifies specific weaknesses:
                  overconfident claims, missing context, factual gaps,
                  unclear recommendations, unsupported severity judgements.

  3. Reviser    — given both the draft AND the critique, produces the final
                  improved assessment. Must address every critique point.

WHAT THE CRITIQUE LOOKS FOR
────────────────────────────
  The critic is specifically instructed to check:
    • Are all risk claims grounded in the fetched data?
    • Is uncertainty acknowledged where the data is incomplete?
    • Is the severity judgement consistent with CVSS + EPSS + KEV together?
    • Is the recommended action specific and actionable?
    • Are there missing caveats (e.g. network-only exploitability, auth required)?

RUN THIS FILE
─────────────
  python architectures/a3_reflection.py
  python architectures/a3_reflection.py CVE-2021-44228
  python architectures/a3_reflection.py CVE-2014-0160
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


# ─── OUTPUT SCHEMAS ───────────────────────────────────────────────────────────

class DraftAssessment(_Base):
    """
    Initial CVE risk assessment produced by the researcher agent.

    This is the first-pass output — accurate but potentially incomplete.
    The critique will identify what it misses or overstates.
    """
    cve_id:             str
    cvss_score:         float
    cvss_severity:      str
    epss_score:         float     = Field(ge=0.0, le=1.0)
    in_cisa_kev:        bool
    patch_available:    bool
    risk_summary:       str       = Field(description="2–3 sentence risk narrative")
    recommended_action: str
    confidence:         str       = Field(description="high / medium / low — how confident are you in this assessment?")


class CritiqueReport(_Base):
    """
    Self-critique produced by the critic agent.

    The critique is the mechanism by which the agent identifies its own
    weaknesses BEFORE the user sees the output.
    """
    overall_quality:    str       = Field(description="good / adequate / poor")
    issues:             list[str] = Field(description="Specific problems found in the draft")
    missing_context:    list[str] = Field(description="Information that should have been included")
    overstatements:     list[str] = Field(description="Claims that go beyond what the data supports")
    improvement_needed: bool      = Field(description="Is revision needed or is the draft acceptable?")
    critique_summary:   str       = Field(description="One-paragraph summary of the critique")


class ReflectionReport(_Base):
    """
    Final report after reflection — draft + critique → revised output.

    Every field should be better than the corresponding draft field because
    the reviser had the critique to address.
    """
    cve_id:             str
    cvss_score:         float
    cvss_severity:      str
    epss_score:         float         = Field(ge=0.0, le=1.0)
    epss_percentile:    float         = Field(ge=0.0, le=1.0)
    in_cisa_kev:        bool
    patch_available:    bool
    risk_summary:       str           = Field(description="Improved 2–3 sentence risk narrative addressing critique")
    recommended_action: str           = Field(description="Specific, actionable recommendation")
    confidence:         str           = Field(description="high / medium / low")
    changes_from_draft: list[str]     = Field(description="What was improved vs the draft, per the critique")
    data_sources:       list[str]


# ─── TOOL IMPLEMENTATIONS ─────────────────────────────────────────────────────
# Same tools as A1/A2. The research phase uses all three.

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
        return {
            "source": "NVD", "cve_id": cve_id, "description": desc,
            "cvss_score": cvss_score, "severity": severity,
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
                "required_action": match.get("requiredAction"),
                "note": f"CONFIRMED ACTIVE EXPLOITATION. Added {match.get('dateAdded')}.",
            }
        return {"source": "CISA KEV", "in_kev": False, "note": f"Not in KEV ({len(vulns)} entries checked)."}
    except Exception as e:
        return {"error": str(e)}


# ─── PHASE 1: RESEARCH ────────────────────────────────────────────────────────

async def research_cve(cve_id: str) -> tuple[DraftAssessment, dict]:
    """
    Phase 1: fetch live data and produce an initial draft assessment.

    The researcher fetches all three data sources in parallel (no dependency
    between them), then synthesises a draft report. This draft will be
    critiqued in phase 2.
    """
    console.print(f"[dim]  Phase 1: Fetching data for {cve_id}...[/dim]")

    nvd_data, epss_data, kev_data = await asyncio.gather(
        fetch_nvd_data(cve_id),
        fetch_epss_score(cve_id),
        check_cisa_kev(cve_id),
    )

    raw_data = {"nvd": nvd_data, "epss": epss_data, "cisa_kev": kev_data}

    response = await client.chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a CVE researcher. Your job is to produce an initial risk assessment "
                    "based on the provided data. Be factual and grounded. Acknowledge uncertainty "
                    "where the data is incomplete. This draft will be reviewed and improved."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Produce an initial risk assessment for {cve_id} based on this data:\n\n"
                    f"{json.dumps(raw_data, indent=2)}"
                ),
            },
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name":   "DraftAssessment",
                "strict": True,
                "schema": _strict_schema(DraftAssessment),
            },
        },
        temperature=0.2,
        max_tokens=1024,
    )
    _track(response)
    draft = DraftAssessment.model_validate(json.loads(response.choices[0].message.content))
    return draft, raw_data


# ─── PHASE 2: CRITIQUE ────────────────────────────────────────────────────────

async def critique_draft(draft: DraftAssessment, raw_data: dict) -> CritiqueReport:
    """
    Phase 2: the critic reviews the draft assessment.

    The critic has access to both the draft AND the raw data, so it can
    identify claims in the draft that aren't supported by the data.

    The adversarial framing ("your job is to find problems") is intentional —
    it produces more specific and actionable critiques than neutral evaluation.
    """
    console.print(f"[dim]  Phase 2: Critic reviewing draft...[/dim]")

    response = await client.chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are an adversarial security analyst reviewing a CVE assessment written by a colleague. "
                    "Your ONLY job is to find problems with the assessment. Be specific and harsh. "
                    "Check for:\n"
                    "  • Claims not supported by the raw data\n"
                    "  • Missing context that would change the risk picture\n"
                    "  • Overconfident language where uncertainty is warranted\n"
                    "  • Vague recommendations that can't be acted on\n"
                    "  • Severity judgements inconsistent with CVSS + EPSS + KEV combined\n"
                    "  • Missing caveats (auth required? network only? interaction needed?)\n"
                    "Do not be polite. Be specific. A good critique makes the revision better."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Raw data collected:\n{json.dumps(raw_data, indent=2)}\n\n"
                    f"Draft assessment to critique:\n{json.dumps(draft.model_dump(), indent=2)}"
                ),
            },
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name":   "CritiqueReport",
                "strict": True,
                "schema": _strict_schema(CritiqueReport),
            },
        },
        temperature=0.3,
        max_tokens=1024,
    )
    _track(response)
    return CritiqueReport.model_validate(json.loads(response.choices[0].message.content))


# ─── PHASE 3: REVISION ────────────────────────────────────────────────────────

async def revise_draft(
    cve_id: str,
    draft: DraftAssessment,
    critique: CritiqueReport,
    raw_data: dict,
) -> ReflectionReport:
    """
    Phase 3: the reviser produces the final report, addressing the critique.

    The reviser sees all three: the original draft, the critique, and the
    raw data. It must address each critique point and record what changed.

    If the critique found no significant issues, the reviser can confirm
    the draft is already solid and make only minor improvements.
    """
    console.print(f"[dim]  Phase 3: Revising based on critique...[/dim]")

    response = await client.chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a senior CVE analyst producing a final risk report. "
                    "You have a draft assessment and a critique of that draft. "
                    "Your job is to produce an improved final report that addresses every issue "
                    "raised in the critique. For each change you make, record it in changes_from_draft. "
                    "Ground all claims in the raw data. Be specific and actionable."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"CVE: {cve_id}\n\n"
                    f"Raw data:\n{json.dumps(raw_data, indent=2)}\n\n"
                    f"Original draft:\n{json.dumps(draft.model_dump(), indent=2)}\n\n"
                    f"Critique:\n{json.dumps(critique.model_dump(), indent=2)}\n\n"
                    "Produce the final improved report."
                ),
            },
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name":   "ReflectionReport",
                "strict": True,
                "schema": _strict_schema(ReflectionReport),
            },
        },
        temperature=0.1,
        max_tokens=2048,
    )
    _track(response)
    return ReflectionReport.model_validate(json.loads(response.choices[0].message.content))


# ─── MAIN PIPELINE ────────────────────────────────────────────────────────────

async def analyse_cve(
    cve_id: str,
) -> tuple[DraftAssessment, CritiqueReport, ReflectionReport]:
    """
    Full Reflection pipeline: research → critique → revise.

    Returns all three stages so the UI can show the improvement process,
    not just the final result. Seeing the draft alongside the final report
    makes the quality improvement tangible.
    """
    _reset_usage()
    console.print(f"\n[dim]  Starting Reflection analysis of {cve_id}...[/dim]")
    start = time.perf_counter()

    draft, raw_data = await research_cve(cve_id)
    critique        = await critique_draft(draft, raw_data)

    if critique.improvement_needed:
        console.print(f"[dim]  Critique found {len(critique.issues)} issue(s). Revising...[/dim]")
    else:
        console.print(f"[dim]  Critique: draft is acceptable. Minor polish only.[/dim]")

    final = await revise_draft(cve_id, draft, critique, raw_data)

    elapsed = time.perf_counter() - start
    console.print(f"[dim]  Completed in {elapsed:.1f}s (3 LLM calls)[/dim]")

    return draft, critique, final


# ─── DISPLAY HELPERS ──────────────────────────────────────────────────────────

SEVERITY_COLOURS = {
    "CRITICAL": "bold red",
    "HIGH":     "red",
    "MEDIUM":   "yellow",
    "LOW":      "green",
}


def display_draft(draft: DraftAssessment) -> None:
    console.print("\n[bold dim]── Draft Assessment (before critique) ───────────────────────────[/bold dim]")
    console.print(Panel(
        f"[dim]Risk summary: {draft.risk_summary}\n\n"
        f"Action: {draft.recommended_action}\n\n"
        f"Confidence: {draft.confidence}[/dim]",
        title=f"[bold]Draft — {draft.cve_id}[/bold]  CVSS {draft.cvss_score} ({draft.cvss_severity})",
        border_style="dim yellow",
        padding=(0, 1),
    ))


def display_critique(critique: CritiqueReport) -> None:
    quality_colour = {"good": "green", "adequate": "yellow", "poor": "red"}.get(
        critique.overall_quality.lower(), "white"
    )
    console.print("\n[bold dim]── Critique ───────────────────────────────────────────────────────[/bold dim]")

    content = f"[{quality_colour}]Overall: {critique.overall_quality}[/{quality_colour}]  "
    content += f"[dim]Revision needed: {'yes' if critique.improvement_needed else 'no'}[/dim]\n\n"

    if critique.issues:
        content += "[bold]Issues:[/bold]\n"
        for issue in critique.issues:
            content += f"  [red]• {issue}[/red]\n"

    if critique.overstatements:
        content += "\n[bold]Overstatements:[/bold]\n"
        for o in critique.overstatements:
            content += f"  [yellow]• {o}[/yellow]\n"

    if critique.missing_context:
        content += "\n[bold]Missing context:[/bold]\n"
        for m in critique.missing_context:
            content += f"  [dim]• {m}[/dim]\n"

    console.print(Panel(content.strip(), title="[bold]Critic's Assessment[/bold]", border_style="dim red", padding=(0, 1)))


def display_final(report: ReflectionReport) -> None:
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
    t.add_row("Confidence",      report.confidence)
    t.add_row("Data Sources",    ", ".join(report.data_sources))
    t.add_row("",                "")
    t.add_row("Risk Summary",    report.risk_summary)
    t.add_row("",                "")
    t.add_row("Recommended",     report.recommended_action)

    if report.changes_from_draft:
        t.add_row("",             "")
        t.add_row("[dim]Changes vs draft[/dim]", "")
        for change in report.changes_from_draft:
            t.add_row("", f"[dim]↑ {change}[/dim]")

    console.print(Panel(
        t,
        title=f"[bold]Final Report (after reflection) — {report.cve_id}[/bold]",
        border_style=colour.replace("bold ", ""),
        padding=(1, 2),
    ))


# ─── ENTRY POINT ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    cve_id = sys.argv[1] if len(sys.argv) > 1 else "CVE-2021-44228"

    console.print()
    console.print(Text("VIGIL", style="bold cyan") + Text(" — Architecture 3: Reflection / Self-Critique", style="dim"))
    console.print(f"[dim]Model: {MODEL}  |  CVE: {cve_id}[/dim]")
    console.print(f"[dim]Pattern: Draft → Critique → Revise  (3 LLM calls)[/dim]")

    draft, critique, final = asyncio.run(analyse_cve(cve_id))

    display_draft(draft)
    display_critique(critique)
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
