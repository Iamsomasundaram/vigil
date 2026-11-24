"""
VIGIL Foundations F6 — Prompt Engineering Techniques
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from collections import Counter
from typing import Any, Awaitable, Callable

from openai import AsyncOpenAI
from rich.console import Console
from rich.table import Table

from vigil.pricing import estimate_cost_usd

console = Console()
MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

_usage: dict = {"prompt_tokens": 0, "completion_tokens": 0}


def _reset_usage() -> None:
    global _usage
    _usage = {"prompt_tokens": 0, "completion_tokens": 0}


def _track(response: Any) -> None:
    if hasattr(response, "usage") and response.usage:
        _usage["prompt_tokens"] += response.usage.prompt_tokens or 0
        _usage["completion_tokens"] += response.usage.completion_tokens or 0


def get_usage() -> dict:
    pt = _usage["prompt_tokens"]
    ct = _usage["completion_tokens"]
    return {
        "prompt_tokens": pt,
        "completion_tokens": ct,
        "total_tokens": pt + ct,
        "estimated_cost_usd": round(estimate_cost_usd(MODEL, pt, ct), 6),
    }


def render(template: str, **vars: str) -> str:
    """Tiny prompt-template renderer used in the F6 demos."""
    return template.format(**vars)


def fence_untrusted(text: str) -> str:
    """Isolate untrusted text using explicit delimiters."""
    return f"<UNTRUSTED_CVE_TEXT>\n{text}\n</UNTRUSTED_CVE_TEXT>"


def zero_shot(cve_id: str, advisory_text: str = "") -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": "You are a cybersecurity analyst. Classify severity as Critical/High/Medium/Low and explain briefly.",
        },
        {
            "role": "user",
            "content": render(
                "Classify the likely severity for {cve_id}. Evidence:\n{evidence}",
                cve_id=cve_id,
                evidence=fence_untrusted(advisory_text or "No extra advisory text supplied."),
            ),
        },
    ]


def few_shot(cve_id: str, advisory_text: str = "") -> list[dict[str, str]]:
    examples = [
        ("CVE-EX-1", "Unauth RCE with public exploit", "Critical"),
        ("CVE-EX-2", "Auth-required XSS in admin UI", "Medium"),
        ("CVE-EX-3", "Info leak with no code exec", "Low"),
    ]
    exemplar_block = "\n".join(f"{cid}: {desc} -> {sev}" for cid, desc, sev in examples)
    return [
        {
            "role": "system",
            "content": "You are a cybersecurity analyst. Learn from the labeled examples and classify the new CVE.",
        },
        {
            "role": "user",
            "content": render(
                "Examples:\n{examples}\n\nNow classify {cve_id}. Evidence:\n{evidence}",
                examples=exemplar_block,
                cve_id=cve_id,
                evidence=fence_untrusted(advisory_text or "No extra advisory text supplied."),
            ),
        },
    ]


def chain_of_thought(cve_id: str, advisory_text: str = "") -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": "Think step by step about exploitability, impact, and patchability, then output final severity with one-sentence rationale.",
        },
        {
            "role": "user",
            "content": render(
                "Analyse {cve_id}. Evidence:\n{evidence}",
                cve_id=cve_id,
                evidence=fence_untrusted(advisory_text or "No extra advisory text supplied."),
            ),
        },
    ]


async def _complete(
    client: AsyncOpenAI,
    messages: list[dict[str, str]],
    *,
    temperature: float = 0.1,
    model: str = MODEL,
) -> tuple[str, dict[str, int]]:
    resp = await client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=280,
    )
    _track(resp)
    pt = (resp.usage.prompt_tokens if resp.usage else 0) or 0
    ct = (resp.usage.completion_tokens if resp.usage else 0) or 0
    return (resp.choices[0].message.content or "").strip(), {"prompt": pt, "completion": ct}


def _extract_vote(text: str) -> str:
    lower = text.lower()
    for sev in ("critical", "high", "medium", "low"):
        if sev in lower:
            return sev.title()
    return "Unknown"


async def self_consistency(
    cve_id: str,
    advisory_text: str,
    *,
    n: int = 5,
    complete_fn: Callable[[list[dict[str, str]], float], Awaitable[str]] | None = None,
) -> dict[str, Any]:
    """Sample multiple generations and majority-vote the severity."""
    temps = [0.2 + (i * 0.1) for i in range(n)]
    base_messages = chain_of_thought(cve_id, advisory_text)

    outputs: list[str] = []
    if complete_fn is not None:
        for t in temps:
            outputs.append(await complete_fn(base_messages, t))
    else:
        client = AsyncOpenAI(timeout=45.0)
        for t in temps:
            out, _ = await _complete(client, base_messages, temperature=t)
            outputs.append(out)

    votes = Counter(_extract_vote(o) for o in outputs)
    label, count = votes.most_common(1)[0]
    return {
        "majority_label": label,
        "vote_share": round(count / max(1, n), 3),
        "samples": outputs,
    }


async def prompt_compare(cve_id: str, advisory_text: str = "") -> dict[str, Any]:
    client = AsyncOpenAI(timeout=45.0)
    _reset_usage()

    techniques: list[tuple[str, list[dict[str, str]]]] = [
        ("zero_shot", zero_shot(cve_id, advisory_text)),
        ("few_shot", few_shot(cve_id, advisory_text)),
        ("chain_of_thought", chain_of_thought(cve_id, advisory_text)),
    ]

    results: list[dict[str, Any]] = []
    for name, messages in techniques:
        out, usage = await _complete(client, messages)
        results.append(
            {
                "technique": name,
                "output": out,
                "tokens": usage["prompt"] + usage["completion"],
                "est_cost_usd": round(estimate_cost_usd(MODEL, usage["prompt"], usage["completion"]), 6),
            }
        )

    sc = await self_consistency(cve_id, advisory_text)
    results.append(
        {
            "technique": "self_consistency",
            "output": f"Majority={sc['majority_label']} ({sc['vote_share']*100:.0f}%)",
            "tokens": 0,
            "est_cost_usd": 0.0,
        }
    )

    return {
        "task": "cve_severity_classification",
        "results": results,
        "notes": "Few-shot adds examples; CoT adds reasoning instruction; self-consistency majority-votes multiple samples.",
    }


def render_comparison_table(payload: dict[str, Any]) -> None:
    t = Table(title="F6 Prompt Technique Comparison")
    t.add_column("Technique")
    t.add_column("Tokens")
    t.add_column("Est. cost (USD)")
    t.add_column("Output preview")
    for row in payload.get("results", []):
        t.add_row(
            str(row.get("technique", "")),
            str(row.get("tokens", "")),
            f"{float(row.get('est_cost_usd', 0.0)):.6f}",
            str(row.get("output", ""))[:80],
        )
    console.print(t)


def main() -> None:
    parser = argparse.ArgumentParser(description="F6 prompt engineering comparison")
    parser.add_argument("cve_id", nargs="?", default="CVE-2021-44228")
    parser.add_argument("--text", default="")
    args = parser.parse_args()

    payload = asyncio.run(prompt_compare(args.cve_id, args.text))
    render_comparison_table(payload)
    console.print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
