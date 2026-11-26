"""
Run-result and score-report schemas.

The tester (P1.3 and P1.4) produces a ``RunResult``; the scorer reads exactly this shape.
"""

from __future__ import annotations

from enum import Enum
from pydantic import BaseModel, Field, model_validator


class Category(str, Enum):
    """The failure taxonomy every verdict uses."""

    PASS = "pass"
    FAIL_APP_DEFECT = "fail_app_defect"
    FAIL_AUTOMATION = "fail_automation_issue"
    FAIL_TEST_DATA = "fail_test_data_issue"
    BLOCKED_ENVIRONMENT = "blocked_environment"
    SKIPPED_OUT_OF_SCOPE = "skipped_out_of_scope"
    EXPLORATORY = "exploratory_observation"
    NEEDS_CLARIFICATION = "needs_business_clarification"
    NEEDS_REVIEW = "needs_review"


# Categories that need no evidence reference (a verdict that changes nothing and claims nothing).
_NO_EVIDENCE_NEEDED = {Category.SKIPPED_OUT_OF_SCOPE}


class Verdict(BaseModel):
    """One judgment: about a formal case (``TC-03``) or a free observation (``OBS-1``)."""

    subject_id: str = Field(description="A case id such as TC-03, or an observation id such as OBS-1")
    category: Category
    confidence: float = Field(ge=0.0, le=1.0)
    summary: str = ""
    tags: list[str] = Field(default_factory=list)
    evidence_ref: str | None = Field(default=None, description="Screenshot, trace or log reference")

    @model_validator(mode="after")
    def _evidence_required(self) -> "Verdict":
        if self.category not in _NO_EVIDENCE_NEEDED and not self.evidence_ref:
            raise ValueError("every verdict except 'skipped' must carry an evidence_ref")
        return self


class RunResult(BaseModel):
    """Everything one tester run produced, for one demo-shop profile."""

    profile: str
    verdicts: list[Verdict]
    cost_usd_estimate: float | None = Field(
        default=None, description="Estimate from indicative list prices; not a bill"
    )
    steps: int | None = None


class IssueScore(BaseModel):
    id: str
    kind: str
    status: str = Field(description="found | missed | silent_false_pass")
    detail: str = ""


class ScoreReport(BaseModel):
    """The answer-key report. ``None`` means the metric does not apply (nothing to measure)."""

    profile: str
    defect_recall: float | None
    false_defect_rate: float | None
    false_defects: list[str]
    classification_accuracy: float | None
    accuracy_by_expected_category: dict[str, float]
    silent_false_passes: int
    exploratory_found: int
    exploratory_total: int
    exploratory_noise: int
    review_volume: int
    cases_not_run: list[str]
    issues: list[IssueScore]
    cost_usd_estimate: float | None = None
    steps: int | None = None
