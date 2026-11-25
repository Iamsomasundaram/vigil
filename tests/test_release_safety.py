from __future__ import annotations

import pytest

from reliability.r9_release_safety import evaluate_release, shadow_compare


def test_evaluate_release_rolls_back_on_regression():
    out = evaluate_release(
        control_scores=[0.80, 0.82, 0.79],
        treatment_scores=[0.70, 0.71, 0.69],
    )
    assert out["decision"] == "rollback"
    assert out["rollback_triggered"] is True


def test_evaluate_release_promotes_on_improvement():
    out = evaluate_release(
        control_scores=[0.70, 0.72, 0.71],
        treatment_scores=[0.80, 0.82, 0.79],
    )
    assert out["decision"] == "promote"
    assert out["next_stage"] == "full"


def test_evaluate_release_requires_scores():
    with pytest.raises(ValueError):
        evaluate_release(control_scores=[], treatment_scores=[0.8])


def test_shadow_compare_safety_flag():
    out = shadow_compare(live_scores=[0.80, 0.81], shadow_scores=[0.80, 0.82])
    assert out["shadow_safe_to_canary"] is True


def test_rollback_returns_traffic_to_stable():
    from reliability.r9_release_safety import evaluate_release

    out = evaluate_release(control_scores=[0.9, 0.9], treatment_scores=[0.5, 0.5])
    assert out["decision"] == "rollback"
    assert out["next_stage"] == "stable"
