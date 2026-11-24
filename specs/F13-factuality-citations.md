# F13 — Factuality, Hallucination, and Citation Verification

- **Status:** Done
- **Axis:** Foundations (GenAI literacy)
- **Target:** reliability + foundations teaching layer
- **Depends on:** R1, R2, F11

---

## Problem / Motivation

Guardrails and evals exist, but learners still need explicit practice spotting
unsupported claims and measuring faithfulness against cited sources.

## Teaching Goal

**A learner can identify unsupported statements and compute a simple faithfulness
score from citation coverage.**

## Goals

- Build a citation verifier utility that maps claims to retrieved evidence spans.
- Teach abstain behavior when evidence is missing.
- Add a hands-on example showing fluent but unsupported output.

## Non-Goals

- Full formal verification.

## Proposed Files

- **New** `levels/foundations/factuality.py`.
- **Edit** `vigil/api.py` (`POST /foundations/factuality-check`).
- **Edit** `ui/app.py` add a factuality lab page.
- **New** `tests/test_factuality.py`.

## Acceptance Criteria

- [x] Claims are labeled supported/unsupported with evidence snippets.
- [x] Faithfulness score is stable and test-covered.
- [x] UI explains when to abstain instead of over-claim.



