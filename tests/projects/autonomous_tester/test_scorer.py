from __future__ import annotations

import pytest
from pydantic import ValidationError

from projects.autonomous_tester.cases import case_ids
from projects.autonomous_tester.evals.answer_key import load_answer_key
from projects.autonomous_tester.evals.models import Category, RunResult, Verdict
from projects.autonomous_tester.evals.scorer import format_report, score

EVID = "trace/run-1"


def v(subject: str, category: Category, summary: str = "", tags: list[str] | None = None) -> Verdict:
    return Verdict(subject_id=subject, category=category, confidence=0.9, summary=summary, tags=tags or [], evidence_ref=EVID)


def perfect(profile: str) -> RunResult:
    """What a flawless tester would report: the correct category for every case, every exploratory issue."""
    key = load_answer_key()
    verdicts = [v(c, key.expected_case_category(c, profile)) for c in sorted(case_ids())]
    n = 0
    for issue in key.active(profile):
        if issue.detectable_by == "exploratory":
            n += 1
            verdicts.append(v(f"OBS-{n}", Category.EXPLORATORY, summary=issue.match_terms[0]))
    return RunResult(profile=profile, verdicts=verdicts, cost_usd_estimate=0.12, steps=40)


@pytest.mark.parametrize("profile", ["clean", "all_bugs", "env_down", "v2_markup"])
def test_a_flawless_run_scores_perfectly(profile):
    report = score(perfect(profile))
    assert report.classification_accuracy == 1.0
    assert report.silent_false_passes == 0
    assert report.false_defects == []
    assert report.cases_not_run == []
    assert report.exploratory_found == report.exploratory_total
    assert report.exploratory_noise == 0
    assert all(i.status == "found" for i in report.issues)
    if profile == "all_bugs":
        assert report.defect_recall == 1.0
    if profile == "clean":
        assert report.defect_recall is None and report.false_defect_rate is None  # nothing to measure


def replace(result: RunResult, subject: str, category: Category) -> RunResult:
    verdicts = [v(subject, category) if x.subject_id == subject else x for x in result.verdicts]
    return result.model_copy(update={"verdicts": verdicts})


def test_passing_the_trap_case_is_a_silent_false_pass():
    result = replace(perfect("all_bugs"), "TC-04", Category.PASS)  # the weak case passes, B05 missed
    report = score(result)
    assert report.silent_false_passes == 1
    assert next(i for i in report.issues if i.id == "B05").status == "silent_false_pass"
    assert report.defect_recall == pytest.approx(4 / 5)
    assert report.classification_accuracy == pytest.approx(9 / 10)


def test_a_missing_verdict_is_missed_not_a_silent_pass():
    result = perfect("all_bugs")
    result = result.model_copy(update={"verdicts": [x for x in result.verdicts if x.subject_id != "TC-03"]})
    report = score(result)
    assert report.silent_false_passes == 0
    assert next(i for i in report.issues if i.id == "B01").status == "missed"
    assert report.cases_not_run == ["TC-03"]


def test_a_defect_raised_on_the_clean_shop_is_a_false_defect():
    result = replace(perfect("clean"), "TC-05", Category.FAIL_APP_DEFECT)
    report = score(result)
    assert report.false_defects == ["TC-05"]
    assert report.false_defect_rate == 1.0
    assert report.classification_accuracy == pytest.approx(9 / 10)


def test_wrong_category_lowers_accuracy_but_is_not_a_false_defect_when_not_a_defect():
    """A data issue reported as an automation issue is wrong, yet not a false *defect*."""
    result = replace(perfect("all_bugs"), "TC-07", Category.FAIL_AUTOMATION)
    report = score(result)
    assert report.false_defects == []
    assert report.classification_accuracy == pytest.approx(9 / 10)
    assert report.accuracy_by_expected_category["fail_test_data_issue"] == 0.5  # TC-01 right, TC-07 wrong


def test_an_app_defect_on_a_data_issue_case_is_a_false_defect():
    result = replace(perfect("all_bugs"), "TC-07", Category.FAIL_APP_DEFECT)
    assert score(result).false_defects == ["TC-07"]


def test_exploration_must_not_raise_defects():
    result = perfect("all_bugs")
    result.verdicts.append(v("OBS-99", Category.FAIL_APP_DEFECT, summary="console error"))
    report = score(result)
    assert "OBS-99" in report.false_defects


def test_observations_that_match_nothing_are_noise_and_matches_are_found():
    result = perfect("all_bugs")
    result.verdicts.append(v("OBS-50", Category.EXPLORATORY, summary="the footer looks plain"))
    report = score(result)
    assert report.exploratory_noise == 1
    assert report.exploratory_found == report.exploratory_total == 3

    on_clean = perfect("clean")
    on_clean.verdicts.append(v("OBS-1", Category.EXPLORATORY, summary="console error seen"))
    assert score(on_clean).exploratory_noise == 1  # nothing is seeded, so any observation is noise


def test_review_volume_counts_escalations():
    result = replace(perfect("all_bugs"), "TC-02", Category.NEEDS_REVIEW)
    result = replace(result, "TC-05", Category.NEEDS_CLARIFICATION)
    assert score(result).review_volume == 2


def test_env_down_cases_blocked_by_the_cart_are_scored_as_blocked():
    report = score(perfect("env_down"))
    assert report.accuracy_by_expected_category["blocked_environment"] == 1.0


def test_verdict_validation():
    with pytest.raises(ValidationError):
        Verdict(subject_id="TC-01", category=Category.FAIL_APP_DEFECT, confidence=0.9)  # no evidence
    with pytest.raises(ValidationError):
        Verdict(subject_id="TC-01", category=Category.PASS, confidence=1.5, evidence_ref="x")  # out of range
    Verdict(subject_id="TC-01", category=Category.SKIPPED_OUT_OF_SCOPE, confidence=1.0)  # skipped needs no evidence


def test_report_text_and_passthrough():
    text = format_report(score(perfect("all_bugs")))
    assert "Defect recall" in text and "100%" in text and "not a bill" in text
    assert "Silent false passes:     0" in text
    assert score(perfect("all_bugs")).cost_usd_estimate == 0.12
