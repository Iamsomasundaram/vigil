"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  VIGIL — Level 1: Prompt Chain                                             ║
║                                                                              ║
║  Three LLM calls in sequence.                                                ║
║  The output of each step becomes the input to the next.                      ║
╚══════════════════════════════════════════════════════════════════════════════╝

CONCEPTS COVERED
────────────────
  1. Prompt chaining       — output of step N feeds step N+1
  2. Structured output     — forcing the LLM to return typed JSON via Pydantic
  3. Context accumulation  — each step builds on what came before
  4. Separation of concerns — each step does ONE focused job

WHY CHAINS BEAT ONE BIG PROMPT
────────────────────────────────
  Asking one prompt to "explain the CVE, assess the risk, AND write a
  remediation plan" produces mediocre results for all three.

  A chain of three focused prompts produces:
    Step 1 — deep, accurate CVE explanation
    Step 2 — risk assessment INFORMED by step 1's findings
    Step 3 — remediation plan TAILORED to step 2's risk level

  Each step gets the model's full attention. This is "divide and conquer"
  applied to prompt engineering.

WHAT IS STRUCTURED OUTPUT?
────────────────────────────
  By default, LLMs return free-form text. That's fine for humans to read
  but unreliable for code to process.

  Structured output = you define a Pydantic model, pass it as
  `response_format`, and the OpenAI SDK guarantees the response matches
  your schema. No parsing. No regex. No surprises.

RUN THIS FILE
─────────────
  python levels/l1_chain.py
  python levels/l1_chain.py CVE-2023-44487
"""

import json
import os
import sys
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel, ConfigDict, Field
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

client = OpenAI(timeout=60.0)
MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

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


# ─── STEP 1 SCHEMA: CVE Summary ───────────────────────────────────────────────
# Instead of free-form text, we define exactly what we want back.
# The LLM MUST return JSON that matches this shape.
#
# Field() lets us add validation rules:
#   ge=0.0  → greater than or equal to 0
#   le=10.0 → less than or equal to 10
#
# Literal["A", "B"] → the model can only return one of these exact strings.
# This eliminates typos like "CRITCAL" or "high" when you expected "High".

class CVESummary(_Base):
    cve_id: str
    one_line_description: str
    affected_product: str
    affected_versions: list[str]
    attack_vector: Literal["Network", "Adjacent Network", "Local", "Physical"]
    authentication_required: bool
    severity: Literal["Critical", "High", "Medium", "Low"]
    cvss_score: float = Field(ge=0.0, le=10.0)


# ─── STEP 2 SCHEMA: Risk Assessment ───────────────────────────────────────────
# This model captures the risk in a way that directly informs step 3.
# Notice it asks for urgency as a concrete SLA, not just a label.

class RiskAssessment(_Base):
    severity: Literal["Critical", "High", "Medium", "Low"]
    urgency: Literal["Patch immediately", "Patch within 24h", "Patch within 7 days", "Patch within 30 days", "Monitor"]
    exploitability_summary: str
    potential_damage_summary: str
    risk_score: int = Field(ge=1, le=10, description="Composite risk score 1-10")
    should_escalate_to_management: bool


# ─── STEP 3 SCHEMA: Remediation Plan ──────────────────────────────────────────
# The plan is tailored to what steps 1 and 2 revealed.
# Concrete action steps that a team can actually follow.

class RemediationPlan(_Base):
    immediate_actions: list[str] = Field(description="Do these in the next hour")
    short_term_actions: list[str] = Field(description="Do these within the SLA window")
    patch_available: bool
    patch_version: str | None = Field(default=None)
    workaround: str | None = Field(default=None, description="If no patch, what can teams do?")
    estimated_effort: Literal["Low", "Medium", "High"]
    rollback_plan: str


# ─── HELPER: Structured LLM Call ──────────────────────────────────────────────
# A thin wrapper that enforces JSON Schema output via the stable chat.completions API.
#
# Why not client.beta.chat.completions.parse()?
#   The beta `parse()` helper is convenient but uses an internal retry/validation
#   loop that can behave differently across SDK versions and environments.
#
# This approach is more explicit and equally powerful:
#   1. Pass the Pydantic model's JSON schema as response_format
#   2. Receive guaranteed JSON from the model
#   3. Parse and validate it with model_validate()
#
# The result is the same typed Pydantic object — just constructed manually.

def call_llm(system: str, user: str, response_model):
    """
    Call the LLM and return a validated Pydantic object.

    The key difference from L0:
      L0 → response is a free-form string
      L1 → response is a typed Python object: result.severity, result.cvss_score, etc.
    """
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ],
        # response_format with json_schema tells the model to return valid JSON
        # matching the exact schema — no parsing surprises, no extra validation loop.
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name":   response_model.__name__,
                "strict": True,
                "schema": _strict_schema(response_model),
            },
        },
        temperature=0.1,
        max_tokens=8192,
    )
    _track(response)
    raw = response.choices[0].message.content
    return response_model.model_validate(json.loads(raw))


# ─── STEP 1: Summarise the CVE ────────────────────────────────────────────────

def step1_summarise(cve_id: str) -> CVESummary:
    """Extract structured facts about the CVE. Also resets the usage accumulator — always the first call in the chain."""
    _reset_usage()
    return call_llm(
        system="You are a CVE analyst. Extract structured facts about the given CVE accurately.",
        user=f"Provide a structured summary of {cve_id}.",
        response_model=CVESummary,
    )


# ─── STEP 2: Assess the Risk ──────────────────────────────────────────────────
# Notice: we pass the full step 1 output into step 2.
# The risk assessment is INFORMED by what we learned about the CVE.
# This is context accumulation — each step knows what came before.

def step2_assess_risk(summary: CVESummary) -> RiskAssessment:
    """Assess risk based on the CVE summary from step 1."""
    return call_llm(
        system="You are a risk analyst. Assess the real-world risk of this vulnerability for enterprise environments.",
        user=f"""Based on this CVE summary, assess the risk:

CVE ID:            {summary.cve_id}
Description:       {summary.one_line_description}
Affected product:  {summary.affected_product} ({', '.join(summary.affected_versions)})
Attack vector:     {summary.attack_vector}
Auth required:     {summary.authentication_required}
CVSS Score:        {summary.cvss_score} ({summary.severity})

Provide a concrete risk assessment with urgency SLA.""",
        response_model=RiskAssessment,
    )


# ─── STEP 3: Build Remediation Plan ───────────────────────────────────────────
# Step 3 receives BOTH previous outputs.
# The plan is tailored to the specific CVE + the assessed risk level.

def step3_remediation(summary: CVESummary, risk: RiskAssessment) -> RemediationPlan:
    """Build a remediation plan tailored to the CVE and its risk level."""
    return call_llm(
        system="You are a security operations lead. Create practical remediation plans teams can execute immediately.",
        user=f"""Create a remediation plan for this vulnerability:

CVE:          {summary.cve_id} — {summary.one_line_description}
Product:      {summary.affected_product} {summary.affected_versions}
Risk Score:   {risk.risk_score}/10
Urgency:      {risk.urgency}
Damage Risk:  {risk.potential_damage_summary}
Escalate:     {risk.should_escalate_to_management}

Provide immediate actions, short-term steps, patch guidance, and a rollback plan.""",
        response_model=RemediationPlan,
    )


# ─── DISPLAY HELPERS ──────────────────────────────────────────────────────────

SEVERITY_COLOURS = {
    "Critical": "bold red",
    "High":     "red",
    "Medium":   "yellow",
    "Low":      "green",
}

def display_results(summary: CVESummary, risk: RiskAssessment, plan: RemediationPlan) -> None:
    colour = SEVERITY_COLOURS.get(summary.severity, "white")

    # ── Summary table ──
    t = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
    t.add_column(style="dim", width=22)
    t.add_column()
    t.add_row("CVE",             f"[bold]{summary.cve_id}[/bold]")
    t.add_row("Description",     summary.one_line_description)
    t.add_row("Affected",        f"{summary.affected_product}  {', '.join(summary.affected_versions)}")
    t.add_row("Attack vector",   summary.attack_vector)
    t.add_row("CVSS score",      f"[{colour}]{summary.cvss_score}  ({summary.severity})[/{colour}]")
    t.add_row("Auth required",   "Yes" if summary.authentication_required else "No")
    console.print(Panel(t, title="[bold]Step 1 — CVE Summary[/bold]", border_style="blue"))

    # ── Risk table ──
    r = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
    r.add_column(style="dim", width=22)
    r.add_column()
    r.add_row("Risk score",      f"[{colour}]{risk.risk_score}/10[/{colour}]")
    r.add_row("Urgency",         f"[bold]{risk.urgency}[/bold]")
    r.add_row("Exploitability",  risk.exploitability_summary)
    r.add_row("Potential damage",risk.potential_damage_summary)
    r.add_row("Escalate?",       "[bold red]Yes[/bold red]" if risk.should_escalate_to_management else "No")
    console.print(Panel(r, title="[bold]Step 2 — Risk Assessment[/bold]", border_style="yellow"))

    # ── Remediation ──
    lines = []
    lines.append("[bold]Immediate actions (next hour):[/bold]")
    for action in plan.immediate_actions:
        lines.append(f"  [red]•[/red] {action}")
    lines.append("")
    lines.append("[bold]Short-term actions:[/bold]")
    for action in plan.short_term_actions:
        lines.append(f"  [yellow]•[/yellow] {action}")
    lines.append("")
    if plan.patch_available:
        lines.append(f"[bold]Patch:[/bold]  {plan.patch_version or 'available — check vendor advisory'}")
    else:
        lines.append(f"[bold]Workaround:[/bold]  {plan.workaround or 'None available yet'}")
    lines.append(f"[bold]Effort:[/bold]  {plan.estimated_effort}")
    lines.append(f"[bold]Rollback:[/bold]  {plan.rollback_plan}")
    console.print(Panel("\n".join(lines), title="[bold]Step 3 — Remediation Plan[/bold]", border_style="green"))


# ─── ENTRY POINT ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    cve_id = sys.argv[1] if len(sys.argv) > 1 else "CVE-2021-44228"

    console.print()
    console.print(f"[bold cyan]VIGIL[/bold cyan] [dim]— Level 1: Prompt Chain[/dim]")
    console.print(f"[dim]Model: {MODEL}  |  CVE: {cve_id}  |  3 chained calls[/dim]\n")

    # ── The chain: 3 sequential LLM calls ──────────────────────────────────
    # Notice how each step's output feeds the next.
    # This is the core of prompt chaining.

    with console.status("[cyan]Step 1/3 — Summarising CVE...[/cyan]"):
        summary = step1_summarise(cve_id)

    with console.status("[cyan]Step 2/3 — Assessing risk...[/cyan]"):
        risk = step2_assess_risk(summary)          # ← receives step 1 output

    with console.status("[cyan]Step 3/3 — Building remediation plan...[/cyan]"):
        plan = step3_remediation(summary, risk)    # ← receives step 1 + 2 outputs

    display_results(summary, risk, plan)
    console.print()
