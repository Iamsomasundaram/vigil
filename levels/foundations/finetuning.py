"""
VIGIL Foundations F21 — Fine-tuning, Adapters, and Build-vs-Tune Decisions
"""

from __future__ import annotations

import argparse
import json
from typing import Any

from rich.console import Console

console = Console()

# Approaches ordered by typical cost/effort, cheapest first.
_APPROACHES = ["prompt_only", "few_shot", "rag", "fine_tune_lora", "full_fine_tune"]


def recommend_approach(
    *,
    task_stability: str = "stable",
    data_volume: int = 0,
    needs_fresh_knowledge: bool = False,
    strict_format: bool = False,
    latency_sensitive: bool = False,
    domain_shift: str = "low",
) -> dict[str, Any]:
    """Recommend an adaptation strategy from task characteristics.

    Heuristic teaching model, not a substitute for empirical evaluation.
    """
    reasons: list[str] = []
    scores: dict[str, float] = {a: 0.0 for a in _APPROACHES}

    # Fresh/changing knowledge favors retrieval over baked-in weights.
    if needs_fresh_knowledge:
        scores["rag"] += 2.0
        reasons.append("fresh knowledge favors RAG over weight updates")
    else:
        scores["fine_tune_lora"] += 0.5

    # Strict output format and stable behavior favor fine-tuning.
    if strict_format and task_stability == "stable":
        scores["fine_tune_lora"] += 1.5
        reasons.append("strict, stable format is a strong fine-tune signal")
    elif strict_format:
        scores["few_shot"] += 1.0
        reasons.append("strict format but unstable task favors few-shot first")

    # Data volume gates fine-tuning viability.
    if data_volume >= 1000:
        scores["fine_tune_lora"] += 1.5
        reasons.append("sufficient labeled data supports LoRA fine-tuning")
    elif data_volume >= 100:
        scores["few_shot"] += 1.0
        reasons.append("small data suits few-shot exemplars")
    else:
        scores["prompt_only"] += 1.0
        reasons.append("little/no data favors prompt engineering first")

    # Latency-sensitive deployments prefer smaller tuned models over long prompts.
    if latency_sensitive:
        scores["fine_tune_lora"] += 0.5
        scores["prompt_only"] += 0.5
        reasons.append("latency pressure favors shorter prompts or tuned models")

    # Large domain shift can justify heavier tuning.
    if domain_shift == "high" and data_volume >= 1000:
        scores["full_fine_tune"] += 1.0
        reasons.append("large domain shift with ample data may justify full fine-tune")

    # Baseline: prompt_only always slightly favored (start simple).
    scores["prompt_only"] += 0.5

    recommended = max(scores, key=lambda k: scores[k])
    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)

    return {
        "recommended": recommended,
        "ranked": [{"approach": a, "score": round(s, 3)} for a, s in ranked],
        "reasons": reasons,
        "guidance": _guidance_for(recommended),
    }


def _guidance_for(approach: str) -> str:
    return {
        "prompt_only": "Start with prompt engineering and evaluation; cheapest and fastest to iterate.",
        "few_shot": "Add curated exemplars; measure lift before considering training.",
        "rag": "Ground answers in retrieval; update the corpus instead of retraining.",
        "fine_tune_lora": "Use parameter-efficient LoRA adapters once data and format are stable.",
        "full_fine_tune": "Reserve full fine-tuning for large domain shifts with strong data and budget.",
    }.get(approach, "Re-evaluate task characteristics.")


def validate_finetune_dataset(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Validate a chat-style fine-tuning dataset for common quality issues."""
    total = len(records)
    valid = 0
    issues: list[str] = []
    seen: set[str] = set()
    duplicates = 0
    empty_completions = 0
    role_errors = 0

    for i, rec in enumerate(records, 1):
        msgs = rec.get("messages") if isinstance(rec, dict) else None
        if not isinstance(msgs, list) or len(msgs) < 2:
            role_errors += 1
            continue

        roles = [m.get("role") for m in msgs if isinstance(m, dict)]
        if "user" not in roles or "assistant" not in roles:
            role_errors += 1
            continue

        assistant_text = " ".join(
            str(m.get("content", "")).strip()
            for m in msgs
            if isinstance(m, dict) and m.get("role") == "assistant"
        ).strip()
        if not assistant_text:
            empty_completions += 1
            continue

        fingerprint = json.dumps(msgs, sort_keys=True)
        if fingerprint in seen:
            duplicates += 1
            continue
        seen.add(fingerprint)
        valid += 1

    if role_errors:
        issues.append(f"{role_errors} record(s) missing valid user/assistant roles")
    if empty_completions:
        issues.append(f"{empty_completions} record(s) with empty assistant content")
    if duplicates:
        issues.append(f"{duplicates} duplicate record(s)")

    quality = round(valid / total, 4) if total else 0.0
    ready = total >= 10 and quality >= 0.9 and duplicates == 0

    return {
        "total": total,
        "valid": valid,
        "duplicates": duplicates,
        "empty_completions": empty_completions,
        "role_errors": role_errors,
        "quality_score": quality,
        "ready_to_train": ready,
        "issues": issues,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="F21 build-vs-tune advisor")
    parser.add_argument("--data-volume", type=int, default=1500)
    parser.add_argument("--fresh-knowledge", action="store_true", default=False)
    parser.add_argument("--strict-format", action="store_true", default=True)
    args = parser.parse_args()

    rec = recommend_approach(
        data_volume=args.data_volume,
        needs_fresh_knowledge=args.fresh_knowledge,
        strict_format=args.strict_format,
    )
    console.print(json.dumps(rec, indent=2))


if __name__ == "__main__":
    main()
