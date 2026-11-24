# F20 — Release Safety: Shadow, Canary, and Rollback

- **Status:** Done
- **Axis:** Reliability and operations
- **Target:** deployment safety for model/prompt/retrieval changes
- **Depends on:** R2, R3, F14, F17

---

## Problem / Motivation

Production GenAI systems now commonly deploy via shadow/canary patterns with
fast rollback. This is critical for reducing blast radius when changing prompts,
models, tools, or retrieval strategies.

## Teaching Goal

**A learner can run a staged rollout, compare treatment vs control, and trigger
rollback from objective guardrails.**

## Goals

- Add shadow-mode evaluation path without user impact.
- Add canary traffic split with metric comparison.
- Add rollback policy and runbook automation hooks.
- Connect with online drift/eval alerts.

## Non-Goals

- Full service mesh or progressive delivery platform integration.

## Proposed Files

- **New** `reliability/r9_release_safety.py`
- **Edit** `vigil/api.py` rollout control endpoints
- **Edit** `ui/app.py` release safety console page
- **New** `tests/test_release_safety.py`

## Acceptance Criteria

- [x] Shadow and canary runs produce comparable scorecards.
- [x] Guardrail breach triggers deterministic rollback in tests.
- [x] UI provides clear rollout state, risk, and recommendation.

