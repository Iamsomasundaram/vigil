# F17 — Online Evaluation and Drift Monitoring

- **Status:** Done
- **Axis:** Reliability and operations
- **Target:** evaluation and observability bridge
- **Depends on:** R2, R3, F14

---

## Problem / Motivation

Offline evals are necessary but insufficient. Production systems need continuous
monitoring for quality drift, data drift, and behavior regressions after model,
prompt, or retrieval changes.

## Teaching Goal

**A learner can set online quality SLOs, detect drift, and trigger rollback or
human review gates when thresholds are crossed.**

## Goals

- Add online eval sampling pipeline with rolling windows.
- Add drift indicators for retrieval, output quality, and latency/cost shifts.
- Add threshold-based alerting and policy actions.
- Integrate with tracing for root-cause analysis.

## Non-Goals

- Full external APM vendor integration.

## Proposed Files

- **New** `reliability/r6_online_eval_drift.py`
- **Edit** `vigil/api.py` endpoints for drift status and evaluation summaries
- **Edit** `ui/app.py` online quality dashboard page
- **New** `tests/test_online_drift.py`

## Acceptance Criteria

- [x] Drift metrics are computed on rolling windows and exposed via API.
- [x] Alert thresholds trigger deterministic actions in tests.
- [x] UI clearly distinguishes transient noise vs sustained drift.

