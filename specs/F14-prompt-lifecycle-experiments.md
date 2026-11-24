# F14 — Prompt Lifecycle, Versioning, and Experiments

- **Status:** Done
- **Axis:** Foundations (GenAI literacy)
- **Target:** foundations + reliability bridge
- **Depends on:** F6, R2

---

## Problem / Motivation

Prompting is taught as one-off craftsmanship, but production teams need repeatable
versioning, replay, A/B tests, and rollback rules.

## Teaching Goal

**A learner can version prompts, run side-by-side experiments, and decide ship/rollback
using objective thresholds.**

## Goals

- Define prompt version records with metadata.
- Add replay on fixed examples and A/B comparison summary.
- Connect to R2-style regression pass/fail guidance.

## Non-Goals

- Full experiment tracking platform.

## Proposed Files

- **New** `levels/foundations/prompt_lifecycle.py`.
- **New** `data/prompts/` sample prompt versions.
- **Edit** `vigil/api.py` prompt lifecycle endpoints.
- **Edit** `ui/app.py` prompt experiment page.
- **New** `tests/test_prompt_lifecycle.py`.

## Acceptance Criteria

- [x] Prompt versions can be listed and compared.
- [x] Replay is deterministic with stubbed model outputs in tests.
- [x] UI shows a clear promote/hold recommendation.



