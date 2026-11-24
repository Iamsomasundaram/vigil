# E3 — Agent-to-Agent Communication (extends A4)

- **Status:** Done
- **Axis:** Extension of Axis 2 (Orchestration) — extends A4 Multi-Agent
- **Extends:** `architectures/a4_multi_agent.py`
- **Depends on:** A4 (orchestrator + parallel specialists)

---

## Problem / Motivation

A4 is a **star topology**: one orchestrator fans out to specialist agents that never
talk to each other; the orchestrator alone synthesizes. Real multi-agent systems let
agents **communicate directly** — hand off work, debate disagreements, and share a
common workspace. These collaboration patterns produce better results on ambiguous
problems and are a core agentic concept A4 doesn't cover.

## Teaching Goal

**A learner sees three collaboration topologies beyond fan-out** — handoff, debate,
and shared blackboard — and observes agents revising their conclusions based on each
other's outputs. They learn that "multi-agent" is a design space, not a single
pattern, and the trade-offs of each.

## Goals

Implement three communication patterns on top of A4's specialists:

1. **Handoff (sequential delegation)** — Threat-Intel agent passes findings to the
   Impact agent, which passes to Remediation; each builds on the prior. Includes an
   explicit handoff message with structured context, not just shared globals.
2. **Debate (peer critique)** — two agents independently assess severity, exchange
   and rebut each other's reasoning over N rounds, then a judge resolves. Surfaces
   disagreement instead of hiding it in averaging.
3. **Blackboard (shared workspace)** — agents read/write a common structured
   workspace; each contributes when it has something to add until the board
   converges (no central orchestrator dictating order).

- A **message bus** abstraction (`AgentMessage`, `send`, `subscribe`) so patterns
  share one communication primitive.
- **Loop limits** on debate/blackboard rounds (ties to the production checklist's
  iteration-limit guardrail).

## Non-Goals

- Distributed/networked agents (all in-process).
- A general agent framework — these are three concrete, teachable topologies.

## Design

```
HANDOFF:   A ──msg──► B ──msg──► C ──► result        (pipeline)

DEBATE:    A ⇄ B  (round 1..N: claim, rebut)  ──► Judge ──► verdict

BLACKBOARD:        ┌──────── shared board ────────┐
                   │  facts | claims | open Qs     │
                   └───▲────────▲────────▲─────────┘
                       A        B        C   (read/write until converged)
```

All three use a common `AgentMessage` envelope (sender, recipient/topic, content,
round). Convergence/termination is bounded by a max-round guardrail.

## Proposed Files

- **Edit** `architectures/a4_multi_agent.py` — add `--mode handoff|debate|blackboard`
  (default keeps current fan-out behavior).
- **New (optional)** `architectures/a4_comms.py` — message bus + blackboard primitive,
  if `a4_multi_agent.py` grows too large.
- **Edit** `vigil/models.py` — `AgentMessage`, `DebateRound`, `Blackboard`, `Consensus`.
- **Edit** `vigil/api.py` — `POST /a4/collaborate` with a `mode` param.
- **New** `tests/test_agent_comms.py`.

## Data Models (`vigil/models.py`)

```python
class AgentMessage(_Base):
    sender: str
    recipient: str            # agent name or "board"
    round: int
    content: str

class DebateRound(_Base):
    round: int
    claims: dict[str, str]    # agent -> claim
    rebuttals: dict[str, str]

class Consensus(_Base):
    mode: Literal["handoff", "debate", "blackboard"]
    transcript: list[AgentMessage]
    rounds_used: int
    final_verdict: str
    disagreement_noted: bool
```

## API & CLI Surface

- `POST /a4/collaborate` — `{cve_id, mode}` → `Consensus` + `TokenUsage`.
- CLI: `python architectures/a4_multi_agent.py CVE-2021-44228 --mode debate`
- CLI: `python architectures/a4_multi_agent.py CVE-2021-44228 --mode blackboard --max-rounds 3`

## Tests (`tests/test_agent_comms.py`)

- Handoff: agent B receives A's structured output in its context.
- Debate: runs exactly N rounds, judge produces a verdict, disagreement flagged when
  claims differ.
- Blackboard: agents converge and the loop terminates at `max_rounds`.
- Message bus delivers to the correct recipient/topic.
- Existing A4 fan-out mode unchanged (regression).

## Acceptance Criteria

- [x] All three topologies run and produce a `Consensus` with a transcript.
- [x] Round limits prevent unbounded loops.
- [x] Disagreement is surfaced, not averaged away (debate mode).
- [x] Default behavior preserves current A4 fan-out.
- [x] Conventions followed; tests stub LLM, no real calls.

## Open Questions

- Judge model for debate — same vs. stronger model? Proposal: configurable, default
  same model to keep cost down.
- Blackboard convergence signal — agent self-declares "nothing to add" vs. a
  controller checks for no-change round? Proposal: no-change round terminates.





