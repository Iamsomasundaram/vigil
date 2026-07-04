from __future__ import annotations

import json
from pathlib import Path

import pytest

from reliability import r2_evaluation as r2


def _write_dataset(tmp_path: Path, rows: list[dict]) -> str:
    path = tmp_path / "golden.json"
    path.write_text(json.dumps(rows), encoding="utf-8")
    return str(path)


def _write_rubric(tmp_path: Path, text: str = "Rubric v1") -> str:
    path = tmp_path / "rubric.md"
    path.write_text(text, encoding="utf-8")
    return str(path)


def _write_baseline(tmp_path: Path, target: str, score: float) -> str:
    path = tmp_path / "baseline.json"
    path.write_text(
        json.dumps({"targets": {target: {"overall_score": score}}}),
        encoding="utf-8",
    )
    return str(path)


def test_deterministic_metric_pass_fail_band_check():
    cases = [
        r2.EvalCase(
            cve_id="CVE-1",
            expected_severity_band=["High", "Critical"],
            expected_kev=False,
            action_required=True,
        ),
        r2.EvalCase(
            cve_id="CVE-2",
            expected_severity_band=["Low"],
            expected_kev=False,
            action_required=False,
        ),
    ]
    outputs = [
        {"severity": "High", "action_required": True, "kev": False},
        {"severity": "Critical", "action_required": False, "kev": False},
    ]

    metric = r2._deterministic_score(cases, outputs)
    assert metric.metric_type == "deterministic"
    assert metric.passed is True
    assert metric.score < 1.0


@pytest.mark.asyncio
async def test_llm_judge_stub_and_scorecard_math(tmp_path: Path):
    dataset = _write_dataset(
        tmp_path,
        [
            {
                "cve_id": "CVE-2021-44228",
                "expected_severity_band": ["High", "Critical"],
                "expected_kev": True,
                "action_required": True,
                "notes": "case",
            }
        ],
    )
    rubric = _write_rubric(tmp_path)
    baseline = _write_baseline(tmp_path, "l2", 0.70)

    async def stub_target(_: str):
        return {
            "severity": "High",
            "kev": True,
            "action_required": True,
            "recommended_action": "Patch immediately.",
            "rationale": "KEV listed.",
        }

    async def stub_judge(case: r2.EvalCase, output: dict, rubric_text: str) -> float:
        assert case.cve_id == "CVE-2021-44228"
        assert "Rubric" in rubric_text
        assert output["severity"] == "High"
        return 4.0

    scorecard = await r2.evaluate(
        target="l2",
        dataset_path=dataset,
        rubric_path=rubric,
        baseline_path=baseline,
        target_fn=stub_target,
        judge_fn=stub_judge,
    )

    assert scorecard.n_cases == 1
    assert len(scorecard.metrics) == 3
    judge_metric = next(m for m in scorecard.metrics if m.metric_type == "llm_judge")
    assert judge_metric.score == 0.8
    assert scorecard.overall_score > 0.0


@pytest.mark.asyncio
async def test_regression_detection_fires_below_threshold(tmp_path: Path):
    dataset = _write_dataset(
        tmp_path,
        [
            {
                "cve_id": "CVE-1",
                "expected_severity_band": ["Critical"],
                "expected_kev": True,
                "action_required": True,
                "notes": None,
            }
        ],
    )
    rubric = _write_rubric(tmp_path)
    baseline = _write_baseline(tmp_path, "l2", 0.95)

    async def poor_target(_: str):
        return {
            "severity": "Low",
            "kev": False,
            "action_required": False,
            "recommended_action": "Monitor only.",
            "rationale": "",
        }

    async def poor_judge(_: r2.EvalCase, __: dict, ___: str) -> float:
        return 1.0

    scorecard = await r2.evaluate(
        target="l2",
        dataset_path=dataset,
        rubric_path=rubric,
        baseline_path=baseline,
        regression_threshold=0.05,
        target_fn=poor_target,
        judge_fn=poor_judge,
    )

    assert scorecard.regression_vs_baseline is not None
    assert scorecard.passed_regression is False


def test_adversarial_metric_detects_poisoned_samples():
    metric = r2._adversarial_metric()
    assert metric.metric_type == "adversarial"
    assert metric.score > 0.0


@pytest.mark.asyncio
async def test_evaluate_accepts_arbitrary_callable_target(tmp_path: Path):
    dataset = _write_dataset(
        tmp_path,
        [
            {
                "cve_id": "CVE-2",
                "expected_severity_band": ["Medium"],
                "expected_kev": False,
                "action_required": True,
                "notes": "callable target check",
            }
        ],
    )
    rubric = _write_rubric(tmp_path)
    baseline = _write_baseline(tmp_path, "l2", 0.2)

    def sync_target(_: str):
        return {
            "severity": "Medium",
            "kev": False,
            "action_required": True,
            "recommended_action": "Apply patch during next window and verify.",
            "rationale": "Exploitability remains plausible.",
        }

    async def judge(_: r2.EvalCase, __: dict, ___: str) -> float:
        return 3.5

    scorecard = await r2.evaluate(
        target="l2",
        dataset_path=dataset,
        rubric_path=rubric,
        baseline_path=baseline,
        target_fn=sync_target,
        judge_fn=judge,
    )
    assert scorecard.n_cases == 1
    assert scorecard.overall_score > 0.0
