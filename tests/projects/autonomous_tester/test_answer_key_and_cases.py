from __future__ import annotations

import pytest
from pydantic import ValidationError

from projects.autonomous_tester.cases import Case, case_ids, load_cases
from projects.autonomous_tester.demo_shop.config import ISSUE_IDS, load_seed, profile_names
from projects.autonomous_tester.evals.answer_key import AnswerKey, Issue, load_answer_key
from projects.autonomous_tester.evals.models import Category


def test_key_ids_match_the_shop_code_in_both_directions():
    key_ids = {i.id for i in load_answer_key().issues}
    assert key_ids == ISSUE_IDS


def test_key_profiles_exist_and_every_profile_is_used():
    key = load_answer_key()
    assert key.profiles() <= set(profile_names())
    assert set(profile_names()) - key.profiles() == {"clean"}  # clean has no issues, by design


def test_covered_cases_exist():
    known = case_ids()
    for issue in load_answer_key().issues:
        assert set(issue.covered_by) <= known, issue.id


def test_seed_targets_name_real_products():
    seed = load_seed()
    skus = {p["sku"] for p in seed["products"]}
    assert set(seed["targets"].values()) <= skus
    assert set(seed["targets"]) <= ISSUE_IDS


def test_every_case_is_used_by_the_key_or_passes_everywhere():
    """A case no issue covers must be a case that passes under every profile (TC-01.. are all covered or clean)."""
    key = load_answer_key()
    covered = {c for i in key.issues for c in i.covered_by}
    for case in case_ids() - covered:
        for profile in profile_names():
            assert key.expected_case_category(case, profile) == Category.PASS


def test_expected_category_by_profile():
    key = load_answer_key()
    assert key.expected_case_category("TC-03", "clean") == Category.PASS
    assert key.expected_case_category("TC-03", "all_bugs") == Category.FAIL_APP_DEFECT
    assert key.expected_case_category("TC-03", "env_down") == Category.BLOCKED_ENVIRONMENT
    assert key.expected_case_category("TC-07", "all_bugs") == Category.FAIL_TEST_DATA
    assert key.expected_case_category("TC-10", "v2_markup") == Category.FAIL_AUTOMATION
    assert key.expected_case_category("TC-04", "all_bugs") == Category.FAIL_APP_DEFECT  # B05: the weak case must still fail


def test_environment_outranks_other_categories_when_issues_overlap():
    base = dict(title="t", active_in=["p"], observe="o", detectable_by="formal")
    key = AnswerKey(
        version=1,
        issues=[
            Issue(id="A", kind="app_defect", covered_by=["TC-X"], expected_verdict="fail_app_defect", **base),
            Issue(id="B", kind="data_issue", covered_by=["TC-X"], expected_verdict="fail_test_data_issue", **base),
            Issue(id="C", kind="environment", covered_by=["TC-X"], expected_verdict="blocked_environment", **base),
        ],
    )
    assert key.expected_case_category("TC-X", "p") == Category.BLOCKED_ENVIRONMENT


def test_key_rejects_inconsistent_entries():
    base = dict(title="t", active_in=["p"], observe="o")
    with pytest.raises(ValidationError):  # kind and expected verdict disagree
        Issue(id="X", kind="app_defect", expected_verdict="blocked_environment", detectable_by="formal", covered_by=["TC-01"], **base)
    with pytest.raises(ValidationError):  # formal issue with no covering case
        Issue(id="X", kind="app_defect", expected_verdict="fail_app_defect", detectable_by="formal", **base)
    with pytest.raises(ValidationError):  # exploratory issue with no match terms
        Issue(id="X", kind="exploratory", expected_verdict="exploratory_observation", detectable_by="exploratory", **base)
    with pytest.raises(ValidationError):  # duplicate ids
        issue = dict(kind="app_defect", expected_verdict="fail_app_defect", detectable_by="formal", covered_by=["TC-01"], **base)
        AnswerKey(version=1, issues=[Issue(id="D", **issue), Issue(id="D", **issue)])


# ─── cases ───────────────────────────────────────────────────────────────────────

def test_cases_load_and_have_unique_ids():
    cases = load_cases()
    assert len(cases) == 10
    assert len({c.id for c in cases}) == 10


def test_cases_never_mention_seeded_issue_ids():
    ids = sorted(ISSUE_IDS)
    for case in load_cases():
        text = " ".join([case.title, case.expected, *case.steps])
        assert not any(i in text for i in ids), case.id


def test_case_validator_rejects_a_seed_id():
    with pytest.raises(ValidationError):
        Case(id="TC-99", title="Check B03", area="cart", priority="P1", steps=["x"], expected="y")


def test_cases_contain_no_selectors_or_code():
    for case in load_cases():
        text = " ".join([case.title, case.expected, *case.steps])
        assert "data-testid" not in text and "<" not in text, case.id
