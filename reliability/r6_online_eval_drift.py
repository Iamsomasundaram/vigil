"""
VIGIL Reliability R6 (F17) — Online Evaluation and Drift Monitoring
"""

from __future__ import annotations

import argparse
import json
import statistics
from typing import Any

from rich.console import Console

console = Console()

# Rolling in-memory window of recent scored samples.
_WINDOW: list[dict[str, float]] = []
_MAX_WINDOW = 200

_DEFAULT_SLO = {
    "min_quality": 0.7,
    "max_latency_ms": 4000.0,
    "max_cost_usd": 0.02,
}


def reset_window() -> None:
    _WINDOW.clear()


def record_sample(*, quality: float, latency_ms: float, cost_usd: float) -> None:
    """Record one production interaction's online-eval sample."""
    _WINDOW.append(
        {
            "quality": max(0.0, min(1.0, float(quality))),
            "latency_ms": max(0.0, float(latency_ms)),
            "cost_usd": max(0.0, float(cost_usd)),
        }
    )
    if len(_WINDOW) > _MAX_WINDOW:
        del _WINDOW[: len(_WINDOW) - _MAX_WINDOW]


def _mean(values: list[float]) -> float:
    return round(statistics.fmean(values), 4) if values else 0.0


def drift_report(*, baseline_quality: float = 0.8, slo: dict[str, float] | None = None) -> dict[str, Any]:
    """Compute drift signals and SLO breaches over the rolling window."""
    active_slo = {**_DEFAULT_SLO, **(slo or {})}
    n = len(_WINDOW)
    if n == 0:
        return {
            "n_samples": 0,
            "slo": active_slo,
            "avg_quality": 0.0,
            "avg_latency_ms": 0.0,
            "avg_cost_usd": 0.0,
            "quality_drift": 0.0,
            "breaches": [],
            "sustained_drift": False,
            "recommended_action": "collect_more_samples",
        }

    qualities = [s["quality"] for s in _WINDOW]
    latencies = [s["latency_ms"] for s in _WINDOW]
    costs = [s["cost_usd"] for s in _WINDOW]

    avg_quality = _mean(qualities)
    avg_latency = _mean(latencies)
    avg_cost = _mean(costs)
    quality_drift = round(avg_quality - baseline_quality, 4)

    breaches: list[str] = []
    if avg_quality < active_slo["min_quality"]:
        breaches.append("quality_below_slo")
    if avg_latency > active_slo["max_latency_ms"]:
        breaches.append("latency_above_slo")
    if avg_cost > active_slo["max_cost_usd"]:
        breaches.append("cost_above_slo")

    # Sustained drift: recent half meaningfully worse than earlier half.
    sustained = False
    if n >= 10:
        half = n // 2
        early = _mean(qualities[:half])
        recent = _mean(qualities[half:])
        sustained = (early - recent) >= 0.1

    if "quality_below_slo" in breaches or sustained:
        action = "rollback_or_human_review"
    elif breaches:
        action = "investigate"
    else:
        action = "healthy"

    return {
        "n_samples": n,
        "slo": active_slo,
        "avg_quality": avg_quality,
        "avg_latency_ms": avg_latency,
        "avg_cost_usd": avg_cost,
        "quality_drift": quality_drift,
        "breaches": breaches,
        "sustained_drift": sustained,
        "recommended_action": action,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="F17 online eval / drift demo")
    parser.add_argument("--samples", type=int, default=12)
    args = parser.parse_args()

    reset_window()
    for i in range(args.samples):
        # Simulate a gradual quality regression for the demo.
        q = 0.85 - (i * 0.02)
        record_sample(quality=q, latency_ms=1200 + i * 50, cost_usd=0.004)

    console.print(json.dumps(drift_report(), indent=2))


if __name__ == "__main__":
    main()
