# F12 — Retrieval Evaluation and Search Metrics

- **Status:** Done
- **Axis:** Foundations (GenAI literacy)
- **Target:** `levels/foundations/retrieval_quality.py` and eval fixtures
- **Depends on:** F11

---

## Problem / Motivation

Learners can retrieve results but cannot quantify retrieval quality. Without metrics,
changes to chunking/indexing are guesswork.

## Teaching Goal

**A learner computes Recall@k and MRR on a tiny labeled retrieval set and can explain
which retrieval configuration is objectively better.**

## Goals

- Add a labeled mini benchmark for retrieval.
- Implement Recall@k, MRR, nDCG in a clear educational helper.
- Compare two retrieval configurations side-by-side.
- Expose metric report in API/UI.

## Non-Goals

- Enterprise-scale benchmark tooling.

## Proposed Files

- **Edit** `levels/foundations/retrieval_quality.py` (metrics helpers).
- **New** `data/eval/retrieval_golden.json`.
- **Edit** `vigil/api.py` (`POST /foundations/retrieval-eval`).
- **Edit** `ui/app.py` add retrieval metrics section.
- **New** `tests/test_retrieval_eval.py`.

## Acceptance Criteria

- [x] Metrics are deterministic and tested.
- [x] Learner can compare two settings and see clear winners.
- [x] API/UI show metric breakdown and interpretation hints.



