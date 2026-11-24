# F18 — Agent Permissions, Sandboxing, and Action Governance

- **Status:** Done
- **Axis:** Reliability and safety
- **Target:** tool use and autonomous action control
- **Depends on:** L4, L6, R1, F10

---

## Problem / Motivation

Modern agent deployments require least-privilege tool access, action scopes, and
execution isolation. Auth alone is not enough; each action path should be policy-
governed and sandboxed.

## Teaching Goal

**A learner can design and enforce action permission policies that prevent unsafe
agent behavior while preserving task completion.**

## Goals

- Add capability-scoped tool permissions per role and task.
- Add sandbox modes for read-only, simulate, and execute.
- Add policy deny/approve logs with rationale.
- Add explicit escalation points for sensitive actions.

## Non-Goals

- Full OS/container sandbox runtime implementation.

## Proposed Files

- **New** `reliability/r7_action_governance.py`
- **Edit** `vigil/api.py` policy-check endpoints
- **Edit** `ui/app.py` permissions and sandbox demo page
- **New** `tests/test_action_governance.py`

## Acceptance Criteria

- [x] Denied actions never execute and produce actionable diagnostics.
- [x] Permission matrix is test-covered by task and role.
- [x] Sandbox modes are visible and auditable in API responses.

