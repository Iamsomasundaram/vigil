"""
VIGIL Reliability R9 (F20) — Release Safety: Shadow, Canary, and Rollback
"""

from __future__ import annotations

import argparse
import json
import statistics
from typing import Any

from rich.console import Console

console = Console()


def _mean(values: list[float]) -> float:
    return round(statistics.fmean(values), 4) if values else 0.0


def evaluate_release(
    *,
    control_scores: list[float],
    treatment_scores: list[float],
    canary_percent: int = 10,
    min_delta: float = -0.02,
) -> dict[str, Any]:
    """Compare control vs treatment for a staged rollout and decide the action.

    ``min_delta`` is the worst acceptable quality change before rollback fires.
    """
    if not control_scores or not treatment_scores:
        raise ValueError("control_scores and treatment_scores must be non-empty")

    control_avg = _mean(control_scores)
    treatment_avg = _mean(treatment_scores)
    delta = round(treatment_avg - control_avg, 4)

    if delta < min_delta:
        decision = "rollback"
        stage = "stable"  # all traffic back on the control version
    elif delta >= 0.0:
        decision = "promote"
        stage = "full"
    else:
        decision = "hold"
        stage = "canary"

    return {
        "canary_percent": int(canary_percent),
        "control_avg": control_avg,
        "treatment_avg": treatment_avg,
        "delta": delta,
        "min_delta": float(min_delta),
        "decision": decision,
        "next_stage": stage,
        "rollback_triggered": decision == "rollback",
    }


def shadow_compare(*, live_scores: list[float], shadow_scores: list[float]) -> dict[str, Any]:
    """Shadow mode: run new variant with zero user impact and compare quality."""
    live_avg = _mean(live_scores)
    shadow_avg = _mean(shadow_scores)
    return {
        "live_avg": live_avg,
        "shadow_avg": shadow_avg,
        "delta": round(shadow_avg - live_avg, 4),
        "shadow_safe_to_canary": shadow_avg >= live_avg - 0.02,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="F20 release safety demo")
    parser.parse_args()

    report = evaluate_release(
        control_scores=[0.80, 0.82, 0.79],
        treatment_scores=[0.74, 0.71, 0.70],
    )
    console.print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
