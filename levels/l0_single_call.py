"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  VIGIL — Level 0: Single LLM Call                                            ║
║                                                                              ║
║  The simplest possible AI interaction.                                       ║
║  One prompt in. One text response out. Nothing else.                         ║
╚══════════════════════════════════════════════════════════════════════════════╝

CONCEPTS COVERED
────────────────
  1. LLM API call    — how to send a message and receive a response
  2. System prompt   — giving the model a role and perspective
  3. User prompt     — the actual question or task
  4. Temperature     — controlling precision vs creativity (0.0 → 1.0)
  5. Max tokens      — capping response length

WHY START HERE?
───────────────
  Every agentic system — no matter how complex — is built on this single
  primitive: call an LLM, get a response. Before adding agents, memory,
  tools, or loops, you need to understand this foundation deeply.

RUN THIS FILE
─────────────
  python levels/l0_single_call.py
  python levels/l0_single_call.py CVE-2023-44487
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

# Load environment variables from .env file
load_dotenv(Path(__file__).parent.parent / ".env")

console = Console()

# ─── CLIENT SETUP ─────────────────────────────────────────────────────────────
# OpenAI() reads OPENAI_API_KEY from the environment automatically.
# You can also pass it explicitly: OpenAI(api_key="sk-...")
client = OpenAI()

# ─── MODEL SELECTION ──────────────────────────────────────────────────────────
# Read model from env, fall back to gpt-4o-mini.
# gpt-4o-mini  = fast, cheap, good enough for most tasks
# gpt-4o       = smarter, slower, more expensive
MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

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


# ─── SYSTEM PROMPT ────────────────────────────────────────────────────────────
# The system prompt sets the model's ROLE, EXPERTISE, and BEHAVIOR.
# Think of it as the job description handed to the model before it starts.
#
# A specific system prompt beats a generic one every time.
# Compare:
#   Bad:  "You are a helpful assistant."
#   Good: "You are a senior security analyst specialising in CVEs. Be precise
#          and factual. Flag when you are uncertain about specific details."
#
# Key principles:
#   - Define the role clearly          → shapes the model's perspective
#   - Set the tone and style           → "concise", "plain English", "factual"
#   - Define what NOT to do            → "avoid exploit code", "say so if unsure"

SYSTEM_PROMPT = """You are a senior cybersecurity analyst specialising in vulnerability management.
Your job is to explain CVEs clearly and concisely to security teams who need to act fast.

Guidelines:
- Use plain English, not jargon
- Be specific about affected systems and versions
- Explain the real-world risk, not just the CVSS score
- Do not provide exploit code or step-by-step attack instructions
- If you are uncertain about specific details of a CVE, say so explicitly"""


def explain_cve(cve_id: str) -> str:
    """
    A single LLM call that explains a CVE in plain English.

    This is Level 0 — the atomic unit of all AI systems.
    Input:  a CVE identifier (e.g. CVE-2021-44228)
    Output: a plain-English explanation as a string
    """

    # ─── USER PROMPT ──────────────────────────────────────────────────────────
    # The user prompt is the specific task for this call.
    # It should be:
    #   - Specific (not "tell me about this CVE" but exactly what you need)
    #   - Structured (use sections/bullets to guide the model's response)
    #   - Bounded (tell the model what scope to stay within)

    user_prompt = f"""Explain {cve_id} for a security team that needs to respond quickly.

Cover the following:
1. What is the vulnerability? (one paragraph, plain English)
2. Which systems and versions are affected?
3. How can it be exploited? (describe the attack vector — no exploit code)
4. What is the severity and why?
5. What should defenders do right now?"""

    # ─── THE API CALL ─────────────────────────────────────────────────────────
    # client.chat.completions.create() is the core OpenAI call.
    #
    # The `messages` list is the conversation history:
    #   {"role": "system"}  → the model's instructions/persona
    #   {"role": "user"}    → what the user (or your code) is asking
    #   {"role": "assistant"} → what the model replied (used in multi-turn)
    #
    # temperature controls randomness:
    #   0.0  → always picks the most likely next token  (precise, deterministic)
    #   1.0  → samples more freely                      (creative, varied)
    #   For factual security analysis: 0.2 is a good balance.
    #
    # max_tokens caps the response length.
    #   1 token ≈ 4 characters in English.
    #   600 tokens ≈ ~450 words — enough for a thorough CVE summary.

    _reset_usage()
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": user_prompt},
        ],
        temperature=0.2,
        max_tokens=600,
    )
    _track(response)

    # ─── EXTRACTING THE RESPONSE ──────────────────────────────────────────────
    # The response is a structured object, not just a string.
    # The actual text lives at: response.choices[0].message.content
    #
    # Why choices[0]?  OpenAI can return multiple completions (n=2, n=3...).
    # We only asked for one (the default), so we always take index 0.

    return response.choices[0].message.content


# ─── ENTRY POINT ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    cve_id = sys.argv[1] if len(sys.argv) > 1 else "CVE-2021-44228"

    console.print()
    console.print(Text("VIGIL", style="bold cyan") + Text(" — Level 0: Single LLM Call", style="dim"))
    console.print(f"[dim]Model: {MODEL}  |  CVE: {cve_id}[/dim]\n")

    with console.status(f"[cyan]Asking the model about {cve_id}...[/cyan]"):
        result = explain_cve(cve_id)

    console.print(Panel(
        result,
        title=f"[bold red]{cve_id}[/bold red]",
        subtitle="[dim]L0 — single LLM call[/dim]",
        border_style="red",
        padding=(1, 2),
    ))
    console.print()
