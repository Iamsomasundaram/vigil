"""
VIGIL Foundations F14 — Prompt Lifecycle and Experiments
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.table import Table

console = Console()


def _default_versions() -> list[dict[str, str]]:
    return [
        {
            "id": "v1",
            "name": "baseline-concise",
            "template": "Classify severity for {item}. Keep answer concise.",
            "notes": "Low-token baseline.",
        },
        {
            "id": "v2",
            "name": "structured-risk-first",
            "template": (
                "Classify severity for {item}. First state severity, then 2 risks, then 2 actions. "
                "Use clear operational wording."
            ),
            "notes": "More structured operational output.",
        },
    ]


def load_prompt_versions(path: str = "data/prompts/f14_prompt_versions.json") -> list[dict[str, str]]:
    p = Path(path)
    if not p.exists():
        return _default_versions()
    payload = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("Prompt versions file must be a JSON list")
    return payload


def list_versions(path: str = "data/prompts/f14_prompt_versions.json") -> list[dict[str, str]]:
    return load_prompt_versions(path)


def _simulate_quality(prompt: str, item: str) -> float:
    """Deterministic educational scorer used for offline experiment replay."""
    text = f"{prompt} {item}".lower()
    score = 0.45
    if "severity" in text:
        score += 0.10
    if "risk" in text:
        score += 0.12
    if "action" in text:
        score += 0.12
    if "structured" in text or "clear" in text:
        score += 0.08
    if len(prompt) < 70:
        score -= 0.04
    return max(0.0, min(1.0, round(score, 4)))


def replay_version(version: dict[str, str], items: list[str]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    total = 0.0
    for item in items:
        rendered = version["template"].format(item=item)
        quality = _simulate_quality(rendered, item)
        rows.append(
            {
                "item": item,
                "rendered_prompt": rendered,
                "quality_score": quality,
                "token_proxy": len(rendered.split()),
            }
        )
        total += quality

    avg = round(total / max(1, len(items)), 4)
    return {
        "version_id": version["id"],
        "version_name": version.get("name", version["id"]),
        "avg_quality": avg,
        "rows": rows,
    }


def compare_versions(
    *,
    version_a: str,
    version_b: str,
    items: list[str],
    path: str = "data/prompts/f14_prompt_versions.json",
) -> dict[str, Any]:
    versions = {v["id"]: v for v in load_prompt_versions(path)}
    if version_a not in versions or version_b not in versions:
        raise ValueError("Unknown version id")

    rep_a = replay_version(versions[version_a], items)
    rep_b = replay_version(versions[version_b], items)

    wins_a = 0
    wins_b = 0
    ties = 0
    per_item: list[dict[str, Any]] = []

    rows_a = {r["item"]: r for r in rep_a["rows"]}
    rows_b = {r["item"]: r for r in rep_b["rows"]}

    for item in items:
        qa = rows_a[item]["quality_score"]
        qb = rows_b[item]["quality_score"]
        if qa > qb:
            winner = "a"
            wins_a += 1
        elif qb > qa:
            winner = "b"
            wins_b += 1
        else:
            winner = "tie"
            ties += 1
        per_item.append({"item": item, "a_quality": qa, "b_quality": qb, "winner": winner})

    if rep_a["avg_quality"] > rep_b["avg_quality"]:
        overall = "a"
    elif rep_b["avg_quality"] > rep_a["avg_quality"]:
        overall = "b"
    else:
        overall = "tie"

    return {
        "version_a": version_a,
        "version_b": version_b,
        "overall_winner": overall,
        "summary": {
            "a_avg_quality": rep_a["avg_quality"],
            "b_avg_quality": rep_b["avg_quality"],
            "a_wins": wins_a,
            "b_wins": wins_b,
            "ties": ties,
        },
        "per_item": per_item,
    }


def render_comparison(payload: dict[str, Any]) -> None:
    t = Table(title="F14 Prompt Lifecycle Comparison")
    t.add_column("Item")
    t.add_column("A")
    t.add_column("B")
    t.add_column("Winner")
    for row in payload.get("per_item", []):
        t.add_row(
            row["item"],
            f"{row['a_quality']:.3f}",
            f"{row['b_quality']:.3f}",
            row["winner"],
        )
    console.print(t)


def main() -> None:
    parser = argparse.ArgumentParser(description="F14 prompt lifecycle compare")
    parser.add_argument("--a", default="v1")
    parser.add_argument("--b", default="v2")
    parser.add_argument(
        "--item",
        action="append",
        default=["CVE-2021-44228", "CVE-2023-44487", "CVE-2014-0160"],
    )
    parser.add_argument("--path", default="data/prompts/f14_prompt_versions.json")
    args = parser.parse_args()

    payload = compare_versions(version_a=args.a, version_b=args.b, items=args.item, path=args.path)
    render_comparison(payload)
    console.print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
