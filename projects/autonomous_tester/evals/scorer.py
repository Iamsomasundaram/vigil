"""
Score one tester run against the answer key.

    python -m projects.autonomous_tester.evals.scorer run_result.json

Rules (kept deliberately simple and deterministic):

* A **case verdict** is one whose ``subject_id`` is a formal case. Its correct category is
  ``AnswerKey.expected_case_category`` (``pass`` when no active issue touches the case).
* An active formal issue is **found** when any covering case has the expected category.
  It is a **silent false pass** when it is not found and a covering case was passed.
* A **false defect** is a ``fail_app_defect`` verdict that the key does not support: on a case
  whose correct category is not an app defect, or on anything that is not a formal case
  (exploration is observation-only and must never raise a defect).
* An active exploratory issue is **found** when an exploratory observation mentions one of its
  ``match_terms``. Observations that match no active issue are **noise**.
  (Term matching is a deterministic baseline; a semantic judge can replace it later.)
"""

from __future__ import annotations

import sys
from pathlib import Path

from projects.autonomous_tester.cases import case_ids
from projects.autonomous_tester.evals.answer_key import AnswerKey, IssueKind, load_answer_key
from projects.autonomous_tester.evals.models import Category, IssueScore, RunResult, ScoreReport, Verdict


def _ratio(numerator: int, denominator: int) -> float | None:
    return None if denominator == 0 else numerator / denominator


def _matches(verdict: Verdict, terms: list[str]) -> bool:
    haystack = " ".join([verdict.summary, *verdict.tags]).lower()
    return any(t.lower() in haystack for t in terms)


def score(result: RunResult, key: AnswerKey | None = None, known_case_ids: frozenset[str] | None = None) -> ScoreReport:
    key = key or load_answer_key()
    known = known_case_ids if known_case_ids is not None else case_ids()
    profile = result.profile

    case_verdicts = [v for v in result.verdicts if v.subject_id in known]
    observations = [v for v in result.verdicts if v.subject_id not in known]
    by_case: dict[str, list[Verdict]] = {}
    for v in case_verdicts:
        by_case.setdefault(v.subject_id, []).append(v)

    # --- per-issue findings -------------------------------------------------------------
    issues: list[IssueScore] = []
    silent = 0
    exploratory_found = 0
    exploratory_total = 0
    matched_observation_ids: set[int] = set()
    for issue in key.active(profile):
        if issue.detectable_by == "formal":
            verdicts = [v for c in issue.covered_by for v in by_case.get(c, [])]
            if any(v.category == issue.expected_verdict for v in verdicts):
                issues.append(IssueScore(id=issue.id, kind=issue.kind.value, status="found"))
            elif any(v.category == Category.PASS for v in verdicts):
                silent += 1
                issues.append(
                    IssueScore(id=issue.id, kind=issue.kind.value, status="silent_false_pass", detail=issue.title)
                )
            else:
                issues.append(IssueScore(id=issue.id, kind=issue.kind.value, status="missed", detail=issue.title))
        else:
            exploratory_total += 1
            hits = [
                (n, v) for n, v in enumerate(observations)
                if v.category == Category.EXPLORATORY and _matches(v, issue.match_terms)
            ]
            if hits:
                exploratory_found += 1
                matched_observation_ids.update(n for n, _ in hits)
                issues.append(IssueScore(id=issue.id, kind=issue.kind.value, status="found"))
            else:
                issues.append(IssueScore(id=issue.id, kind=issue.kind.value, status="missed", detail=issue.title))

    noise = sum(
        1 for n, v in enumerate(observations)
        if v.category == Category.EXPLORATORY and n not in matched_observation_ids
    )

    # --- defect recall ---------------------------------------------------------------------
    app_defects = [i for i in key.active(profile) if i.kind == IssueKind.APP_DEFECT]
    found_ids = {s.id for s in issues if s.status == "found"}
    defect_recall = _ratio(sum(1 for i in app_defects if i.id in found_ids), len(app_defects))

    # --- false defects ---------------------------------------------------------------------
    raised = [v for v in result.verdicts if v.category == Category.FAIL_APP_DEFECT]
    false_defects = [
        v.subject_id for v in raised
        if v.subject_id not in known
        or key.expected_case_category(v.subject_id, profile) != Category.FAIL_APP_DEFECT
    ]

    # --- classification accuracy (case verdicts only) ------------------------------------
    expected = [(v, key.expected_case_category(v.subject_id, profile)) for v in case_verdicts]
    correct = sum(1 for v, exp in expected if v.category == exp)
    per_category: dict[str, tuple[int, int]] = {}
    for v, exp in expected:
        ok, total = per_category.get(exp.value, (0, 0))
        per_category[exp.value] = (ok + (v.category == exp), total + 1)

    return ScoreReport(
        profile=profile,
        defect_recall=defect_recall,
        false_defect_rate=_ratio(len(false_defects), len(raised)),
        false_defects=false_defects,
        classification_accuracy=_ratio(correct, len(case_verdicts)),
        accuracy_by_expected_category={k: ok / total for k, (ok, total) in per_category.items()},
        silent_false_passes=silent,
        exploratory_found=exploratory_found,
        exploratory_total=exploratory_total,
        exploratory_noise=noise,
        review_volume=sum(
            1 for v in result.verdicts if v.category in (Category.NEEDS_REVIEW, Category.NEEDS_CLARIFICATION)
        ),
        cases_not_run=sorted(known - set(by_case)),
        issues=issues,
        cost_usd_estimate=result.cost_usd_estimate,
        steps=result.steps,
    )


def format_report(report: ScoreReport) -> str:
    def pct(x: float | None) -> str:
        return "n/a" if x is None else f"{x:.0%}"

    lines = [
        f"Profile: {report.profile}",
        f"Defect recall:           {pct(report.defect_recall)}",
        f"False-defect rate:       {pct(report.false_defect_rate)}  {report.false_defects or ''}",
        f"Classification accuracy: {pct(report.classification_accuracy)}",
        f"Silent false passes:     {report.silent_false_passes}  (target 0)",
        f"Exploratory found:       {report.exploratory_found}/{report.exploratory_total} (noise: {report.exploratory_noise})",
        f"Review volume:           {report.review_volume}",
        f"Cases not run:           {', '.join(report.cases_not_run) or 'none'}",
    ]
    if report.cost_usd_estimate is not None:
        lines.append(f"Cost (estimate, not a bill): ${report.cost_usd_estimate:.4f}")
    lines.append("Issues:")
    lines += [f"  {i.id:<4} {i.status:<18} {i.detail}" for i in report.issues]
    return "\n".join(lines)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: python -m projects.autonomous_tester.evals.scorer run_result.json")
    print(format_report(score(RunResult.model_validate_json(Path(sys.argv[1]).read_text(encoding="utf-8")))))
