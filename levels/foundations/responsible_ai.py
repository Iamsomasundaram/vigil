"""
VIGIL Foundations F23 — Responsible-AI Evaluation (Bias/Fairness + Moderation)
"""

from __future__ import annotations

import argparse
import json
import re
from typing import Any

from rich.console import Console

console = Console()

# Illustrative moderation lexicon for teaching; not a production classifier.
_MODERATION_PATTERNS: list[tuple[str, str]] = [
    ("hate", r"\b(exterminate|inferior race|subhuman|kill (?:all|every(?:one)?) (?:the )?\w+)\b"),
    ("harassment", r"\b(idiot|stupid|worthless|loser)\b"),
    ("self_harm", r"\b(suicide|self[- ]harm|hurt myself)\b"),
    ("violence", r"\b(bomb|shoot up|massacre)\b"),
    ("sexual", r"\b(explicit sexual|nsfw)\b"),
]

# Group terms used to probe outcome parity across cohorts.
_DEFAULT_GROUPS = ["group_a", "group_b"]


def moderate_text(text: str) -> dict[str, Any]:
    """Flag policy-relevant categories in text via lightweight patterns."""
    lowered = text.lower()
    categories: list[str] = []
    spans: list[str] = []
    for label, pattern in _MODERATION_PATTERNS:
        for m in re.finditer(pattern, lowered):
            categories.append(label)
            spans.append(m.group(0))
    unique = sorted(set(categories))
    return {
        "flagged": bool(unique),
        "categories": unique,
        "matched_spans": sorted(set(spans)),
        "action": "block" if unique else "allow",
    }


def fairness_report(outcomes: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute selection-rate parity across groups (demographic parity).

    Each outcome: {"group": str, "positive": bool}. Returns per-group selection
    rates plus the disparate-impact ratio (min/max) and an 80%-rule flag.
    """
    if not outcomes:
        return {
            "groups": {},
            "min_rate": 0.0,
            "max_rate": 0.0,
            "disparate_impact_ratio": 1.0,
            "passes_80pct_rule": True,
            "n": 0,
        }

    counts: dict[str, dict[str, int]] = {}
    for o in outcomes:
        g = str(o.get("group", "unknown"))
        counts.setdefault(g, {"pos": 0, "total": 0})
        counts[g]["total"] += 1
        if bool(o.get("positive")):
            counts[g]["pos"] += 1

    rates = {g: (c["pos"] / c["total"] if c["total"] else 0.0) for g, c in counts.items()}
    values = list(rates.values())
    max_rate = max(values) if values else 0.0
    min_rate = min(values) if values else 0.0
    ratio = (min_rate / max_rate) if max_rate > 0 else 1.0

    return {
        "groups": {g: round(r, 4) for g, r in rates.items()},
        "min_rate": round(min_rate, 4),
        "max_rate": round(max_rate, 4),
        "disparate_impact_ratio": round(ratio, 4),
        "passes_80pct_rule": ratio >= 0.8,
        "n": len(outcomes),
    }


def responsible_ai_report(
    *,
    texts: list[str] | None = None,
    outcomes: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Combined moderation + fairness report for a batch of samples."""
    texts = texts or []
    moderation = [dict(text=t[:80], **moderate_text(t)) for t in texts]
    flagged = sum(1 for m in moderation if m["flagged"])
    fairness = fairness_report(outcomes or [])

    return {
        "n_texts": len(texts),
        "flagged_texts": flagged,
        "moderation": moderation,
        "fairness": fairness,
        "safe_to_ship": flagged == 0 and fairness["passes_80pct_rule"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="F23 responsible-AI eval demo")
    parser.add_argument("--text", action="append", default=["This tool is great", "You stupid loser"])
    args = parser.parse_args()

    outcomes = [
        {"group": "group_a", "positive": True},
        {"group": "group_a", "positive": True},
        {"group": "group_b", "positive": False},
        {"group": "group_b", "positive": True},
    ]
    report = responsible_ai_report(texts=args.text, outcomes=outcomes)
    console.print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
