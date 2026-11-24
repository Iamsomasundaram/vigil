# F23 — Responsible-AI Evaluation (Bias/Fairness + Moderation)

- **Status:** Done
- **Axis:** Foundations (governance & safety)
- **Target:** `levels/foundations/responsible_ai.py`
- **Depends on:** R1, F15, F18

---

## Problem / Motivation

Guardrails and privacy cover injection and PII, but production GenAI also needs
content moderation and outcome-fairness checks to catch harmful output and biased
decisions before release.

## Teaching Goal

**A learner can screen outputs for policy violations and check outcome parity
across groups, then decide whether a batch is safe to ship.**

## Goals

- Lightweight content moderation across common harm categories.
- Demographic-parity (selection-rate) check with the 80% rule.
- Combined safe-to-ship signal usable as a release gate.
- Deterministic and offline for tests.

## Non-Goals

- Production-grade moderation classifiers or protected-attribute inference.

## Files Delivered

- **New** `levels/foundations/responsible_ai.py`
- **Edit** `vigil/models.py`, `vigil/api.py`, `ui/app.py`
- **New** `tests/test_responsible_ai.py`

## API & CLI Surface

- `POST /foundations/responsible-ai`
- CLI: `python -m levels.foundations.responsible_ai --text "sample"`

## Acceptance Criteria

- [x] Moderation flags harmful categories and allows clean text.
- [x] Fairness check computes disparate-impact ratio and 80%-rule pass/fail.
- [x] Safe-to-ship combines moderation + fairness; tests are deterministic.
