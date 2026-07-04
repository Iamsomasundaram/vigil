# E2 — Human-in-the-Loop Approval Gates (extends A2)

- **Status:** Draft
- **Axis:** Extension of Axis 2 (Orchestration) — extends A2 Plan-and-Execute
- **Extends:** `architectures/a2_plan_execute.py`
- **Depends on:** A2 (plan/execute separation)

---

## Problem / Motivation

A2 produces a clean, human-reviewable plan — then executes it immediately. The whole
_point_ of separating planning from execution in a security context is to insert an
approval gate ("the agent proposes these 4 steps and this remediation — approve?"),
but A2 never actually pauses. Real human-in-the-loop is its own pattern: interrupts,
clarification requests, edits, and approve/reject gates with an audit trail.

## Teaching Goal

**A learner runs an agent that halts at a checkpoint, surfaces its proposed plan/
action, and waits for a human to approve, edit, or reject** before continuing. They
learn the mechanics of pausable agent state, approval gates on high-risk actions, and
why autonomy must be revocable.

## Goals

- **Pausable execution** — the A2 executor can suspend before a gated step, persist
  its state, and resume later with a human decision.
- **Gate types:**
  - **Plan approval** — human reviews/edits the full plan before any step runs.
  - **Action approval** — individual high-risk steps (e.g. "open a P1 ticket",
    "recommend taking a prod service offline") require sign-off.
  - **Clarification request** — the agent can ask the human a question and block on
    the answer.
- **Decisions:** `approve | reject | edit | request_changes`, each recorded with
  actor, timestamp, and rationale (audit trail).
- **Resumable state** — works synchronously (CLI prompt) and asynchronously (API:
  submit plan → human decides later → resume).
- Reuses R1's approval-gate concept for _which_ actions are high-risk.

## Non-Goals

- A full review UI (a minimal Streamlit panel is a stretch goal, not required).
- Multi-approver workflows / RBAC (single approver is enough for the lesson).

## Design

```
PLAN ──► [GATE: plan approval] ──approve──► EXECUTE step 1
            │ edit/reject                      │
            ▼                                  ▼
       revise / abort                  [GATE: action approval?]
                                          │ high-risk → pause
                                          ▼
                                   await human decision
                                          │ approve → run step
                                          │ reject  → skip + log
```

State machine: `pending_plan_approval → executing → pending_action_approval →
executing → done | aborted`. Persisted to PostgreSQL (sync mode keeps it in memory).

## Proposed Files

- **Edit** `architectures/a2_plan_execute.py` — add gates, pause/resume, decision model.
- **Edit** `vigil/models.py` — `ApprovalGate`, `HumanDecision`, `PausedRun`.
- **Edit** `vigil/api.py` — endpoints below.
- **New** `tests/test_human_in_the_loop.py`.
- **(Stretch)** `ui/app.py` — an "Approvals" panel listing pending gates.

## Data Models (`vigil/models.py`)

```python
class ApprovalGate(_Base):
    gate_id: str
    run_id: str
    gate_type: Literal["plan", "action", "clarification"]
    payload: str             # plan text, action description, or question
    risk: Literal["low", "medium", "high"]

class HumanDecision(_Base):
    gate_id: str
    decision: Literal["approve", "reject", "edit", "request_changes"]
    edited_payload: str | None
    rationale: str | None
    actor: str

class PausedRun(_Base):
    run_id: str
    cve_id: str
    state: Literal["pending_plan_approval", "executing",
                   "pending_action_approval", "done", "aborted"]
    open_gate: ApprovalGate | None
```

## API & CLI Surface

- `POST /a2/start` — `{cve_id}` → `PausedRun` (stops at first gate).
- `GET /a2/runs/{run_id}` — current `PausedRun` + open gate.
- `POST /a2/runs/{run_id}/decision` — `HumanDecision` → resumed `PausedRun`.
- CLI (sync): `python architectures/a2_plan_execute.py CVE-2021-44228 --interactive`
  prompts at each gate via `rich`.

## Tests (`tests/test_human_in_the_loop.py`)

- Run pauses at plan-approval before any step executes.
- `approve` resumes; `reject` aborts with audit entry; `edit` replaces the plan.
- High-risk step triggers an action gate; low-risk steps do not.
- Clarification gate blocks until an answer is supplied.
- Async resume restores state correctly (stub DB / in-memory).

## Acceptance Criteria

- [ ] Agent demonstrably halts and waits for a human decision before high-risk steps.
- [ ] All decision types work and are recorded with actor + rationale.
- [ ] Sync (CLI) and async (API) resume paths both function.
- [ ] Conventions followed; tests stub LLM and skip DB gracefully.

## Open Questions

- Where to store paused state in sync mode — in-memory only vs. always DB? Proposal:
  in-memory for CLI, DB for API.
- Timeout/expiry for an unanswered gate? Proposal: configurable; default none for the
  learning project.
