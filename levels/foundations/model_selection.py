"""
VIGIL Foundations F22 — Claude Model Selection & Context Engineering
"""

from __future__ import annotations

import argparse
import json
from typing import Any

from rich.console import Console

console = Console()

# Illustrative Claude tier profiles for teaching model-selection tradeoffs.
# Values are relative teaching proxies, not billing figures.
_CLAUDE_TIERS: dict[str, dict[str, Any]] = {
    "haiku": {
        "name": "Claude Haiku",
        "strengths": ["low latency", "high throughput", "low cost"],
        "best_for": ["classification", "routing", "high-volume simple tasks"],
        "relative_cost": 1,
        "relative_capability": 2,
        "relative_latency": 1,
    },
    "sonnet": {
        "name": "Claude Sonnet",
        "strengths": ["balanced capability/cost", "tool use", "coding"],
        "best_for": ["agents", "RAG synthesis", "most production workloads"],
        "relative_cost": 3,
        "relative_capability": 4,
        "relative_latency": 2,
    },
    "opus": {
        "name": "Claude Opus",
        "strengths": ["deepest reasoning", "complex planning", "hardest tasks"],
        "best_for": ["multi-step planning", "ambiguous analysis", "high-stakes reasoning"],
        "relative_cost": 5,
        "relative_capability": 5,
        "relative_latency": 4,
    },
}


def claude_tiers() -> list[dict[str, Any]]:
    return [{"tier": k, **v} for k, v in _CLAUDE_TIERS.items()]


def recommend_model(
    *,
    task_complexity: str = "medium",
    latency_sensitive: bool = False,
    cost_sensitive: bool = False,
    high_volume: bool = False,
    high_stakes: bool = False,
) -> dict[str, Any]:
    """Recommend a Claude tier from task/operational constraints.

    Heuristic teaching model; real selection should be evaluation-driven.
    """
    scores = {"haiku": 0.0, "sonnet": 0.0, "opus": 0.0}
    reasons: list[str] = []

    if task_complexity == "low":
        scores["haiku"] += 2.0
        reasons.append("low complexity favors Haiku")
    elif task_complexity == "high":
        scores["opus"] += 2.0
        reasons.append("high complexity favors Opus reasoning")
    else:
        scores["sonnet"] += 2.0
        reasons.append("medium complexity favors balanced Sonnet")

    if latency_sensitive:
        scores["haiku"] += 1.5
        reasons.append("latency sensitivity favors Haiku")
    if cost_sensitive:
        scores["haiku"] += 1.0
        scores["sonnet"] += 0.5
        reasons.append("cost sensitivity favors cheaper tiers")
    if high_volume:
        scores["haiku"] += 1.0
        reasons.append("high volume favors throughput of Haiku")
    if high_stakes:
        scores["opus"] += 1.5
        reasons.append("high-stakes correctness favors Opus")

    # Sonnet stays the safe default for balanced production use.
    scores["sonnet"] += 0.75

    recommended = max(scores, key=lambda k: scores[k])
    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)

    return {
        "recommended": recommended,
        "recommended_name": _CLAUDE_TIERS[recommended]["name"],
        "ranked": [{"tier": t, "score": round(s, 3)} for t, s in ranked],
        "reasons": reasons,
        "escalation_hint": "Start on the cheaper tier; escalate to a higher tier only when evals show it is needed.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="F22 Claude model selection advisor")
    parser.add_argument("--complexity", default="medium", choices=["low", "medium", "high"])
    parser.add_argument("--latency", action="store_true", default=False)
    parser.add_argument("--cost", action="store_true", default=False)
    parser.add_argument("--high-stakes", action="store_true", default=False)
    args = parser.parse_args()

    out = recommend_model(
        task_complexity=args.complexity,
        latency_sensitive=args.latency,
        cost_sensitive=args.cost,
        high_stakes=args.high_stakes,
    )
    console.print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
