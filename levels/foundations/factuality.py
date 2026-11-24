"""
VIGIL Foundations F13 — Factuality and Citation Verification
"""

from __future__ import annotations

import argparse
import json
import re
from typing import Any

from rich.console import Console
from rich.table import Table

console = Console()

_STOP = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "in", "is", "it", "of", "on", "or", "that", "the", "to", "with", "this", "these", "those", "was", "were",
}


def _tokens(text: str) -> set[str]:
    terms = re.findall(r"[A-Za-z0-9_\-]+", text.lower())
    out = {t for t in terms if t not in _STOP}
    # Expand common security shorthand so lexical support checks are less brittle.
    if "rce" in out:
        out.update({"remote", "code", "execution"})
    if "dos" in out:
        out.update({"denial", "service"})
    return out


def split_claims(answer_text: str) -> list[str]:
    """Split free-form answer text into sentence-like claims."""
    raw = re.split(r"[.!?]\s+|\n+", answer_text.strip())
    claims = [s.strip(" -\t") for s in raw if s.strip()]
    return claims


def _best_evidence(claim: str, evidence_snippets: list[str]) -> tuple[float, str]:
    claim_terms = _tokens(claim)
    if not claim_terms:
        return 0.0, ""

    best_score = 0.0
    best_excerpt = ""
    for snippet in evidence_snippets:
        snip_terms = _tokens(snippet)
        if not snip_terms:
            continue
        overlap = claim_terms.intersection(snip_terms)
        score = len(overlap) / max(1, len(claim_terms))
        if score > best_score:
            best_score = score
            best_excerpt = snippet
    return best_score, best_excerpt


def factuality_check(
    *,
    answer_text: str,
    evidence_snippets: list[str],
    support_threshold: float = 0.45,
) -> dict[str, Any]:
    """Label claims as supported/unsupported based on lexical overlap with evidence."""
    claims = split_claims(answer_text)
    results: list[dict[str, Any]] = []
    supported = 0

    for claim in claims:
        score, excerpt = _best_evidence(claim, evidence_snippets)
        ok = score >= support_threshold
        if ok:
            supported += 1
        results.append(
            {
                "claim": claim,
                "supported": ok,
                "support_score": round(score, 4),
                "evidence_excerpt": excerpt if ok else "",
            }
        )

    total = len(claims)
    faithfulness = (supported / total) if total else 0.0
    unsupported_claims = [r["claim"] for r in results if not r["supported"]]

    return {
        "faithfulness_score": round(faithfulness, 4),
        "supported_claims": supported,
        "total_claims": total,
        "unsupported_claims": unsupported_claims,
        "abstain_recommended": len(unsupported_claims) > 0,
        "results": results,
    }


def render_factuality_table(report: dict[str, Any]) -> None:
    table = Table(title="F13 Factuality Check")
    table.add_column("Claim")
    table.add_column("Supported")
    table.add_column("Score")
    table.add_column("Evidence")

    for row in report.get("results", []):
        table.add_row(
            row.get("claim", ""),
            "yes" if row.get("supported") else "no",
            f"{float(row.get('support_score', 0.0)):.2f}",
            row.get("evidence_excerpt", "")[:80],
        )
    console.print(table)


def main() -> None:
    parser = argparse.ArgumentParser(description="F13 factuality checker")
    parser.add_argument("--answer", default="Log4j has remote code execution and patch 2.17.1 is available.")
    parser.add_argument(
        "--evidence",
        action="append",
        default=[
            "CVE-2021-44228 allows remote code execution in Apache Log4j.",
            "Patch to Log4j 2.17.1 or later is recommended.",
        ],
    )
    parser.add_argument("--threshold", type=float, default=0.45)
    args = parser.parse_args()

    report = factuality_check(
        answer_text=args.answer,
        evidence_snippets=args.evidence,
        support_threshold=args.threshold,
    )
    render_factuality_table(report)
    console.print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
