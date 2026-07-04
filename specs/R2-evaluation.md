# R2 — Agent Evaluation & Regression Testing

- **Status:** Draft
- **Axis:** 3 — Reliability & Safety
- **Module:** `reliability/r2_evaluation.py`
- **Depends on:** L1–L4 (the things being evaluated)
- **Checklist:** §8 Evaluation & Testing (Evaluation Datasets, Regression Testing, Adversarial Testing, Task-Specific Metrics)

---

## Problem / Motivation

The existing `tests/` suite verifies **plumbing** (does the loop run, are tools
called) by stubbing the LLM. It says nothing about **quality**: is L2's verdict
actually correct? Did tweaking the L3 router prompt make routing worse? Without
evals, every prompt change is a blind gamble — the #1 thing separating a demo from
a production agent.

## Teaching Goal

**A learner builds a golden dataset and an LLM-as-judge, then watches a deliberately
worsened prompt get caught by a regression score.** They learn that you cannot
improve what you do not measure, and that LLM outputs need _graded_, not _exact_,
assertions.

## Goals

- A **golden dataset** format: CVE id + expected facts (severity band, KEV status,
  whether action is required) + rationale, stored as JSON.
- An **evaluator** supporting multiple metric types:
  - **Deterministic** — exact/range checks on structured fields (severity within
    band, SLA within tolerance).
  - **LLM-as-judge** — a grader model scores free-text remediation quality (0–5)
    against a rubric, with the rubric versioned.
  - **Adversarial** — reuses R1 poisoned cases; passing means "not fooled".
- A **regression harness**: run the suite against any level (L1–L4 + later R/E
  modules), produce a scorecard, and compare against a stored baseline; fail if a
  metric drops beyond a threshold.
- Aggregate report with per-metric pass rates, cost, and latency.

## Non-Goals

- A hosted eval dashboard (CLI + JSON report is enough for the learning project).
- Human-labeling tooling.

## Design

```
golden_set.json ──► run target level on each case ──► raw outputs
                                                          │
            ┌─────────────────────────────────────────────┤
            ▼                    ▼                         ▼
   deterministic metrics   llm_judge(rubric)        adversarial check
            └─────────────────────┬───────────────────────┘
                                  ▼
                    Scorecard (per-metric pass %, cost, latency)
                                  ▼
                 compare to baseline.json → PASS / REGRESSION
```

`evaluate(level, dataset)` takes a callable (the level's analyse function) so any
current or future module can be plugged in.

## Proposed Files

- **New** `reliability/r2_evaluation.py` — runner, metrics, judge, scorecard.
- **New** `data/eval/golden_set.json` — labeled CVE cases.
- **New** `data/eval/rubric.md` — versioned grading rubric for the judge.
- **New** `data/eval/baseline.json` — committed baseline scores (regenerated on demand).
- **Edit** `vigil/models.py` — `EvalCase`, `MetricResult`, `Scorecard`.
- **Edit** `vigil/api.py` — `POST /r2/evaluate`.
- **New** `tests/test_evaluation.py`.

## Data Models (`vigil/models.py`)

```python
class EvalCase(_Base):
    cve_id: str
    expected_severity_band: list[str]   # e.g. ["Critical", "High"]
    expected_kev: bool
    action_required: bool
    notes: str | None

class MetricResult(_Base):
    name: str
    metric_type: Literal["deterministic", "llm_judge", "adversarial"]
    score: float          # normalized 0.0–1.0
    passed: bool
    detail: str | None

class Scorecard(_Base):
    target: str           # which level/module was evaluated
    n_cases: int
    metrics: list[MetricResult]
    overall_score: float
    estimated_cost_usd: float
    regression_vs_baseline: float | None
```

## API & CLI Surface

- `POST /r2/evaluate` — `{target, dataset?}` → `Scorecard`.
- CLI: `python reliability/r2_evaluation.py --target l2 --dataset data/eval/golden_set.json`
- CLI: `python reliability/r2_evaluation.py --target l3 --update-baseline`

## Tests (`tests/test_evaluation.py`)

- Deterministic metric correctly passes/fails a severity-band check.
- LLM-judge path uses a stubbed grader returning a fixed score; scorecard math correct.
- Regression detection fires when current score < baseline − threshold.
- Adversarial cases from R1 reduce the score of an unguarded target.
- `evaluate()` accepts an arbitrary callable target.

## Acceptance Criteria

- [ ] Running against L2/L3 produces a `Scorecard` with all three metric types.
- [ ] A deliberately worsened prompt produces a detectable regression vs baseline.
- [ ] Judge rubric is versioned and referenced in the report.
- [ ] Conventions followed; tests use stubs, no real calls.

## Open Questions

- Should the judge use a stronger model than the target (`gpt-4o` judging
  `gpt-4o-mini`)? Proposal: yes, configurable via `OPENAI_JUDGE_MODEL`.
- Baseline storage: committed JSON vs. DB table? Proposal: JSON for portability.
