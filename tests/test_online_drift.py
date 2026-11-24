from __future__ import annotations

from reliability.r6_online_eval_drift import drift_report, record_sample, reset_window


def test_drift_report_healthy_when_quality_high():
    reset_window()
    for _ in range(12):
        record_sample(quality=0.85, latency_ms=1000, cost_usd=0.003)
    rep = drift_report(baseline_quality=0.84)
    assert rep["n_samples"] == 12
    assert rep["recommended_action"] in {"healthy", "investigate"}
    assert "quality_below_slo" not in rep["breaches"]


def test_drift_report_flags_quality_breach():
    reset_window()
    for _ in range(12):
        record_sample(quality=0.4, latency_ms=1000, cost_usd=0.003)
    rep = drift_report()
    assert "quality_below_slo" in rep["breaches"]
    assert rep["recommended_action"] == "rollback_or_human_review"


def test_drift_report_detects_sustained_regression():
    reset_window()
    for _ in range(6):
        record_sample(quality=0.9, latency_ms=1000, cost_usd=0.003)
    for _ in range(6):
        record_sample(quality=0.6, latency_ms=1000, cost_usd=0.003)
    rep = drift_report()
    assert rep["sustained_drift"] is True
