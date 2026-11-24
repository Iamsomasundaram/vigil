# F15 — Privacy, Data Governance, and Safe Logging

- **Status:** Done
- **Axis:** Foundations (GenAI literacy)
- **Target:** reliability-aware foundations module
- **Depends on:** R1, R3, F10

---

## Problem / Motivation

Production GenAI learning is incomplete without privacy controls. Learners need
practical patterns for redaction, retention, and audit-safe logging.

## Teaching Goal

**A learner can classify sensitive fields, redact them before model calls, and verify
that logs and traces remain useful without leaking secrets.**

## Goals

- Add PII/secret pattern detection and redaction helpers.
- Demonstrate trace-safe logging with redacted payload snapshots.
- Provide a retention-policy simulation for stored memory entries.

## Non-Goals

- Legal/compliance automation.

## Proposed Files

- **New** `levels/foundations/privacy.py`.
- **Edit** `vigil/api.py` (`POST /foundations/privacy/redact`).
- **Edit** `ui/app.py` privacy lab page.
- **New** `tests/test_privacy.py`.

## Acceptance Criteria

- [x] Redaction catches common PII/secret formats in tests.
- [x] Safe log snapshots preserve debugging value.
- [x] UI teaches pre-send sanitation as a mandatory step.



