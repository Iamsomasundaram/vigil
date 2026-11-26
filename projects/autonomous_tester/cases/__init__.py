"""Load and validate the plain-language test cases."""

from __future__ import annotations

import re
import yaml
from functools import lru_cache
from pathlib import Path
from pydantic import BaseModel, Field, model_validator

CASES_FILE = Path(__file__).parent / "cases.yaml"

# Cases must never reveal how the shop is seeded (ids like B01, D02, X03 belong to the answer key).
_SEED_ID = re.compile(r"\b[BDEAX]\d{2}\b")


class Case(BaseModel):
    id: str
    title: str
    area: str
    priority: str
    steps: list[str] = Field(min_length=1)
    expected: str

    @model_validator(mode="after")
    def _no_seed_ids(self) -> "Case":
        text = " ".join([self.title, self.expected, *self.steps])
        if _SEED_ID.search(text):
            raise ValueError(f"case {self.id} mentions a seeded-issue id")
        return self


@lru_cache(maxsize=1)
def load_cases(path: Path | None = None) -> tuple[Case, ...]:
    raw = yaml.safe_load((path or CASES_FILE).read_text(encoding="utf-8"))
    cases = tuple(Case(**c) for c in raw["cases"])
    ids = [c.id for c in cases]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate case id")
    return cases


def case_ids() -> frozenset[str]:
    return frozenset(c.id for c in load_cases())
