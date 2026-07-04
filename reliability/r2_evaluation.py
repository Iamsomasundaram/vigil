"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  VIGIL — Reliability R2: Evaluation & Regression Testing                    ║
║                                                                              ║
║  Builds a reusable evaluation harness with deterministic checks,             ║
║  LLM-as-judge scoring, adversarial checks, and baseline regression gates.   ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

from __future__ import annotations

import argparse
import asyncio
import inspect
import json
import os
from pathlib import Path
from typing import Any, Awaitable, Callable

from dotenv import load_dotenv
from openai import AsyncOpenAI
from pydantic import ValidationError
from rich.console import Console
from rich.table import Table

from reliability.r1_guardrails import scan_for_injection
from vigil.models import EvalCase, MetricResult, Scorecard

load_dotenv(Path(__file__).parent.parent / ".env")

console = Console()
MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
JUDGE_MODEL = os.getenv("OPENAI_JUDGE_MODEL", MODEL)
DEFAULT_DATASET = "data/eval/golden_set.json"
DEFAULT_BASELINE = "data/eval/baseline.json"
DEFAULT_RUBRIC = "data/eval/rubric.md"

_usage: dict = {"prompt_tokens": 0, "completion_tokens": 0}
_client: AsyncOpenAI | None = None


def _reset_usage() -> None:
    global _usage
    _usage = {"prompt_tokens": 0, "completion_tokens": 0}


def _track(response: Any) -> None:
    if hasattr(response, "usage") and response.usage:
        _usage["prompt_tokens"] += response.usage.prompt_tokens or 0
        _usage["completion_tokens"] += response.usage.completion_tokens or 0


def get_usage() -> dict:
    pt = _usage["prompt_tokens"]
    ct = _usage["completion_tokens"]
    cost = (pt * 0.150 + ct * 0.600) / 1_000_000
    return {
        "prompt_tokens": pt,
        "completion_tokens": ct,
        "total_tokens": pt + ct,
        "estimated_cost_usd": round(cost, 6),
    }


def _read_text(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def load_eval_cases(dataset_path: str) -> list[EvalCase]:
    raw = json.loads(_read_text(dataset_path))
    if not isinstance(raw, list):
        raise ValueError("Dataset must be a JSON array of cases")
    return [EvalCase.model_validate(item) for item in raw]


def _load_rubric(rubric_path: str) -> str:
    return _read_text(rubric_path)


def _normalize_target_output(target: str, result: Any) -> dict[str, Any]:
    if isinstance(result, dict) and "severity" in result:
        return result

    if target == "l2":
        if not isinstance(result, tuple) or len(result) != 2:
            raise ValueError("Expected L2 target to return (agent_reports, verdict)")
        _, verdict = result
        verdict_dict = verdict.model_dump() if hasattr(verdict, "model_dump") else dict(verdict)
        return {
            "severity": verdict_dict.get("overall_priority", "Medium"),
            "kev": None,
            "action_required": True,
            "recommended_action": " ".join(verdict_dict.get("top_three_actions", [])),
            "rationale": verdict_dict.get("executive_summary", ""),
        }

    if target == "l3":
        if not isinstance(result, tuple) or len(result) != 2:
            raise ValueError("Expected L3 target to return (routing, result)")
        routing, route_result = result
        routing_dict = routing.model_dump() if hasattr(routing, "model_dump") else dict(routing)
        result_dict = route_result.model_dump() if hasattr(route_result, "model_dump") else dict(route_result)
        track = routing_dict.get("track", "needs_human_review")
        severity_map = {
            "critical_response": "Critical",
            "standard_patch": "High",
            "low_risk_monitor": "Low",
            "needs_human_review": "Medium",
        }
        return {
            "severity": severity_map.get(track, "Medium"),
            "kev": None,
            "action_required": track != "low_risk_monitor",
            "recommended_action": str(result_dict.get("recommended_action", "")),
            "rationale": str(routing_dict.get("reason", "")),
        }

    if target == "l4":
        if not isinstance(result, tuple) or len(result) != 2:
            raise ValueError("Expected L4 target to return (analysis, tool_log)")
        analysis, _ = result
        analysis_dict = analysis.model_dump() if hasattr(analysis, "model_dump") else dict(analysis)
        return {
            "severity": analysis_dict.get("cvss_severity", "Medium"),
            "kev": None,
            "action_required": True,
            "recommended_action": str(analysis_dict.get("recommended_action", "")),
            "rationale": str(analysis_dict.get("description", "")),
        }

    if target == "l1":
        if not isinstance(result, dict):
            raise ValueError("Expected L1 target to return dict")
        return {
            "severity": result.get("severity", "Medium"),
            "kev": None,
            "action_required": bool(result.get("action_required", True)),
            "recommended_action": str(result.get("recommended_action", "")),
            "rationale": str(result.get("rationale", "")),
        }

    raise ValueError(f"Unsupported target format for {target}")


def _deterministic_score(cases: list[EvalCase], outputs: list[dict[str, Any]]) -> MetricResult:
    checks = 0
    passed = 0

    for case, out in zip(cases, outputs):
        severity = str(out.get("severity", "")).strip()
        if severity:
            checks += 1
            if severity in case.expected_severity_band:
                passed += 1

        if out.get("kev") is not None:
            checks += 1
            if bool(out.get("kev")) == case.expected_kev:
                passed += 1

        if out.get("action_required") is not None:
            checks += 1
            if bool(out.get("action_required")) == case.action_required:
                passed += 1

    score = (passed / checks) if checks else 0.0
    return MetricResult(
        name="deterministic_quality",
        metric_type="deterministic",
        score=round(score, 4),
        passed=score >= 0.8,
        detail=f"{passed}/{checks} checks passed",
    )


def _heuristic_judge_score(case: EvalCase, output: dict[str, Any]) -> float:
    score = 2.5
    text = (output.get("recommended_action") or "") + " " + (output.get("rationale") or "")
    lowered = text.lower()

    if case.action_required and any(k in lowered for k in ("patch", "mitigate", "upgrade", "remediate")):
        score += 1.5
    if case.expected_kev and "urgent" in lowered:
        score += 0.5
    if len(text.strip()) >= 40:
        score += 0.5

    return max(0.0, min(5.0, score))


async def _llm_judge_score(case: EvalCase, output: dict[str, Any], rubric: str) -> float:
    global _client
    if _client is None:
        _client = AsyncOpenAI(timeout=45.0)

    system = (
        "You are an evaluation judge. Score remediation quality from 0 to 5. "
        "Return strict JSON with key: score."
    )
    user = {
        "rubric": rubric,
        "case": case.model_dump(),
        "output": output,
    }

    response = await _client.chat.completions.create(
        model=JUDGE_MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps(user)},
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "JudgeScore",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {"score": {"type": "number", "minimum": 0, "maximum": 5}},
                    "required": ["score"],
                    "additionalProperties": False,
                },
            },
        },
        temperature=0.0,
        max_tokens=120,
    )
    _track(response)
    payload = json.loads(response.choices[0].message.content)
    score = float(payload.get("score", 0.0))
    return max(0.0, min(5.0, score))


async def _judge_metric(
    cases: list[EvalCase],
    outputs: list[dict[str, Any]],
    rubric: str,
    judge_fn: Callable[[EvalCase, dict[str, Any], str], Awaitable[float]] | None = None,
) -> MetricResult:
    judge_scores: list[float] = []
    effective_judge = judge_fn or _llm_judge_score

    for case, out in zip(cases, outputs):
        try:
            score = await effective_judge(case, out, rubric)
        except Exception:
            score = _heuristic_judge_score(case, out)
        judge_scores.append(score)

    normalized = (sum(judge_scores) / (len(judge_scores) * 5)) if judge_scores else 0.0
    return MetricResult(
        name="llm_judge_quality",
        metric_type="llm_judge",
        score=round(normalized, 4),
        passed=normalized >= 0.7,
        detail=f"average judge score={sum(judge_scores) / len(judge_scores):.2f}/5" if judge_scores else "no cases",
    )


def _adversarial_metric() -> MetricResult:
    fixtures_path = Path(__file__).parent.parent / "data" / "poisoned_cves.json"
    fixtures = json.loads(fixtures_path.read_text(encoding="utf-8"))

    suspicious = 0
    for row in fixtures:
        scan = scan_for_injection(str(row.get("description", "")))
        if scan.is_suspicious:
            suspicious += 1

    score = (suspicious / len(fixtures)) if fixtures else 0.0
    return MetricResult(
        name="adversarial_injection_resistance",
        metric_type="adversarial",
        score=round(score, 4),
        passed=score >= 0.9,
        detail=f"{suspicious}/{len(fixtures)} poisoned samples flagged",
    )


def _load_baseline(baseline_path: str, target: str) -> float | None:
    path = Path(baseline_path)
    if not path.exists():
        return None

    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and "targets" in data:
        target_data = data.get("targets", {}).get(target)
        if isinstance(target_data, dict) and "overall_score" in target_data:
            return float(target_data["overall_score"])
    if isinstance(data, dict) and data.get("target") == target and "overall_score" in data:
        return float(data["overall_score"])
    return None


def _write_baseline(baseline_path: str, target: str, scorecard: Scorecard) -> None:
    path = Path(baseline_path)
    data: dict[str, Any]
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
    else:
        data = {"targets": {}}

    if "targets" not in data or not isinstance(data["targets"], dict):
        data = {"targets": {}}

    data["targets"][target] = {
        "overall_score": scorecard.overall_score,
        "n_cases": scorecard.n_cases,
        "estimated_cost_usd": scorecard.estimated_cost_usd,
        "metrics": [m.model_dump() for m in scorecard.metrics],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _resolve_target(target: str) -> Callable[[str], Any] | Callable[[str], Awaitable[Any]]:
    if target == "l1":
        from levels.l1_chain import step1_summarise, step2_assess_risk, step3_remediation

        def run(cve_id: str) -> dict[str, Any]:
            summary = step1_summarise(cve_id)
            risk = step2_assess_risk(summary)
            plan = step3_remediation(summary, risk)
            return {
                "severity": summary.severity,
                "action_required": bool(risk.should_escalate_to_management or risk.risk_score >= 6),
                "recommended_action": " ".join(plan.immediate_actions[:2]) if plan.immediate_actions else "Review remediation plan.",
                "rationale": risk.exploitability_summary,
            }

        return run

    if target == "l2":
        from levels.l2_parallel import analyse_cve

        return analyse_cve

    if target == "l3":
        from levels.l3_routing import analyse_cve

        return analyse_cve

    if target == "l4":
        from levels.l4_tool_use import analyse_cve

        return analyse_cve

    raise ValueError(f"Unsupported target: {target}. Expected one of: l1, l2, l3, l4")


async def _invoke_target(
    target_fn: Callable[[str], Any] | Callable[[str], Awaitable[Any]],
    cve_id: str,
) -> Any:
    result = target_fn(cve_id)
    if inspect.isawaitable(result):
        return await result
    return result


async def evaluate(
    target: str,
    dataset_path: str = DEFAULT_DATASET,
    rubric_path: str = DEFAULT_RUBRIC,
    baseline_path: str = DEFAULT_BASELINE,
    regression_threshold: float = 0.05,
    target_fn: Callable[[str], Any] | Callable[[str], Awaitable[Any]] | None = None,
    judge_fn: Callable[[EvalCase, dict[str, Any], str], Awaitable[float]] | None = None,
    update_baseline: bool = False,
) -> Scorecard:
    _reset_usage()

    cases = load_eval_cases(dataset_path)
    rubric = _load_rubric(rubric_path)
    resolved_target = target_fn or _resolve_target(target)

    outputs: list[dict[str, Any]] = []
    for case in cases:
        raw = await _invoke_target(resolved_target, case.cve_id)
        outputs.append(_normalize_target_output(target, raw))

    metrics = [
        _deterministic_score(cases, outputs),
        await _judge_metric(cases, outputs, rubric, judge_fn=judge_fn),
        _adversarial_metric(),
    ]

    overall_score = round(sum(m.score for m in metrics) / len(metrics), 4)
    baseline = _load_baseline(baseline_path, target)
    regression = None if baseline is None else round(overall_score - baseline, 4)

    scorecard = Scorecard(
        target=target,
        n_cases=len(cases),
        metrics=metrics,
        overall_score=overall_score,
        estimated_cost_usd=get_usage().get("estimated_cost_usd", 0.0),
        regression_vs_baseline=regression,
        regression_threshold=regression_threshold,
        passed_regression=(regression is None) or (regression >= -regression_threshold),
        rubric_version=Path(rubric_path).name,
    )

    if update_baseline:
        _write_baseline(baseline_path, target, scorecard)

    return scorecard


def _render_scorecard(scorecard: Scorecard) -> None:
    table = Table(title=f"R2 Evaluation — target={scorecard.target}")
    table.add_column("Metric")
    table.add_column("Type")
    table.add_column("Score")
    table.add_column("Pass")
    table.add_column("Detail")

    for m in scorecard.metrics:
        table.add_row(
            m.name,
            m.metric_type,
            f"{m.score:.3f}",
            "YES" if m.passed else "NO",
            m.detail or "",
        )

    console.print(table)
    console.print(f"Overall score: {scorecard.overall_score:.3f}")
    if scorecard.regression_vs_baseline is None:
        console.print("Regression vs baseline: N/A (no baseline)")
    else:
        console.print(f"Regression vs baseline: {scorecard.regression_vs_baseline:+.3f}")
        console.print(f"Regression gate: {'PASS' if scorecard.passed_regression else 'FAIL'}")


def main() -> None:
    parser = argparse.ArgumentParser(description="R2 evaluation harness")
    parser.add_argument("--target", required=True, choices=["l1", "l2", "l3", "l4"])
    parser.add_argument("--dataset", default=DEFAULT_DATASET)
    parser.add_argument("--rubric", default=DEFAULT_RUBRIC)
    parser.add_argument("--baseline", default=DEFAULT_BASELINE)
    parser.add_argument("--threshold", type=float, default=0.05)
    parser.add_argument("--update-baseline", action="store_true")
    args = parser.parse_args()

    try:
        scorecard = asyncio.run(
            evaluate(
                target=args.target,
                dataset_path=args.dataset,
                rubric_path=args.rubric,
                baseline_path=args.baseline,
                regression_threshold=args.threshold,
                update_baseline=args.update_baseline,
            )
        )
        _render_scorecard(scorecard)
    except (ValueError, ValidationError, FileNotFoundError) as e:
        console.print(f"[red]R2 evaluation failed:[/red] {e}")
        raise SystemExit(1) from e


if __name__ == "__main__":
    main()
