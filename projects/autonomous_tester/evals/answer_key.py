"""
The answer key: ground truth for every issue seeded into the demo shop.

The shop reads it to know which issues a profile switches on; the scorer reads it to know
what a correct tester would say. The tester agent must never read it.
"""

from __future__ import annotations

import yaml
from enum import Enum
from functools import lru_cache
from pathlib import Path
from pydantic import BaseModel, Field, model_validator
from typing import Literal

from projects.autonomous_tester.evals.models import Category

KEY_FILE = Path(__file__).parent / "seeded_bugs.yaml"


class IssueKind(str, Enum):
    APP_DEFECT = "app_defect"
    DATA = "data_issue"
    ENVIRONMENT = "environment"
    AUTOMATION = "automation"
    EXPLORATORY = "exploratory"


# A verdict category is fixed by the kind of issue; the key states it explicitly and we check it.
_KIND_TO_CATEGORY = {
    IssueKind.APP_DEFECT: Category.FAIL_APP_DEFECT,
    IssueKind.DATA: Category.FAIL_TEST_DATA,
    IssueKind.ENVIRONMENT: Category.BLOCKED_ENVIRONMENT,
    IssueKind.AUTOMATION: Category.FAIL_AUTOMATION,
    IssueKind.EXPLORATORY: Category.EXPLORATORY,
}

# When one case is touched by several active issues, the first category here wins: an
# environment failure blocks everything behind it, then a stale script, then bad data.
_PRIORITY = [
    Category.BLOCKED_ENVIRONMENT,
    Category.FAIL_AUTOMATION,
    Category.FAIL_TEST_DATA,
    Category.FAIL_APP_DEFECT,
]


class Issue(BaseModel):
    id: str
    kind: IssueKind
    title: str
    active_in: list[str] = Field(min_length=1)
    covered_by: list[str] = Field(default_factory=list)
    expected_verdict: Category
    detectable_by: Literal["formal", "exploratory"]
    observe: str
    match_terms: list[str] = Field(default_factory=list)
    notes: str = ""

    @model_validator(mode="after")
    def _consistent(self) -> "Issue":
        if self.expected_verdict != _KIND_TO_CATEGORY[self.kind]:
            raise ValueError(f"{self.id}: kind {self.kind.value} cannot expect {self.expected_verdict.value}")
        if self.detectable_by == "formal" and not self.covered_by:
            raise ValueError(f"{self.id}: a formal issue must be covered by at least one case")
        if self.detectable_by == "exploratory":
            if self.covered_by:
                raise ValueError(f"{self.id}: an exploratory issue must not be covered by a formal case")
            if not self.match_terms:
                raise ValueError(f"{self.id}: an exploratory issue needs match_terms")
        return self


class AnswerKey(BaseModel):
    version: int
    issues: list[Issue]

    @model_validator(mode="after")
    def _unique_ids(self) -> "AnswerKey":
        ids = [i.id for i in self.issues]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate issue id in the answer key")
        return self

    def active(self, profile: str) -> list[Issue]:
        return [i for i in self.issues if profile in i.active_in]

    def profiles(self) -> set[str]:
        return {p for i in self.issues for p in i.active_in}

    def expected_case_category(self, case_id: str, profile: str) -> Category:
        """What a correct tester concludes for this case under this profile."""
        hits = {i.expected_verdict for i in self.active(profile) if case_id in i.covered_by}
        for category in _PRIORITY:
            if category in hits:
                return category
        return Category.PASS


@lru_cache(maxsize=1)
def load_answer_key(path: Path | None = None) -> AnswerKey:
    return AnswerKey(**yaml.safe_load((path or KEY_FILE).read_text(encoding="utf-8")))
