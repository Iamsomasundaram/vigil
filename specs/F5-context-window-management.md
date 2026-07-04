# F5 — Context-Window Management (extends L5)

- **Status:** Implemented
- **Axis:** Foundations (GenAI literacy) — extends Axis-1 memory
- **Extends:** `levels/l5_memory.py` (memory context builder)
- **Depends on:** L5 (memory), F4 (token counting), R5 (budgets)

---

## Problem / Motivation

L5 injects **all** prior history as raw text. The project's own readiness checklist marks
every "Context Window Management" item as a gap: no summarization fallback, no truncation
policy, no compaction, no near-limit detection. In production this is exactly where
agents break — histories grow until they blow the context window or crowd out fresh
evidence. A learner must see how to keep an agent coherent under a fixed token budget.

## Teaching Goal

**A learner caps the memory context to a token budget and watches the agent summarize
and prioritize older history instead of failing.** They learn truncation vs
summarization vs compaction, priority ordering of context, and near-limit detection.

## Goals

- **Token-budgeted context** — `build_memory_context` accepts a `max_tokens` budget
  (uses F4 counting) and never exceeds it.
- **Priority ordering** — system rules > fresh tool evidence > recent memory > old memory;
  drop/condense from the bottom first.
- **Summarization fallback** — when history exceeds budget, LLM-summarize older entries
  into a compact "lessons learned" block (consolidation), keeping recent entries verbatim.
- **Compaction store** — persist consolidated summaries so repeated runs stay cheap
  (ties to E1 memory consolidation).
- **Near-limit signal** — response reports `context_tokens`, `budget`, `was_truncated`,
  `was_summarized`.

## Non-Goals

- Cross-session "agent handoff" continuity (future spec).
- A general document-RAG retriever (that's F1/doc-RAG).

## Design

```
history ─► order by priority ─► fits budget?
   yes → inject verbatim
   no  → keep recent K verbatim + summarize the rest ─► compact block ─► fits budget
         (persist summary for reuse) ; report truncation/summarization flags
```

## Proposed Files

- **Edit** `levels/l5_memory.py` — budgeted `build_memory_context`, `summarize_history()`,
  `consolidate_old_memories()`, near-limit reporting.
- **Edit** `vigil/models.py` — `ContextBudgetReport`.
- **Edit** `vigil/api.py` — L5 analyse response includes `context_budget`.
- **New** `tests/test_context_window.py` — budget never exceeded; summary path triggers.
- **Edit** `ui/app.py` — L5 page shows a context-budget meter.

## Data Models (`vigil/models.py`)

```python
class ContextBudgetReport(_Base):
    budget_tokens: int
    used_tokens: int
    entries_verbatim: int
    entries_summarized: int
    was_truncated: bool
    was_summarized: bool
```

## API & CLI Surface

- L5 analyse response gains `context_budget: ContextBudgetReport`.
- CLI: `python levels/l5_memory.py CVE-2021-44228 --max-context-tokens 1200`.
- Env: `VIGIL_MEMORY_TOKEN_BUDGET` (default e.g. 1500).

## Tests (`tests/test_context_window.py`)

- Context never exceeds the configured budget (counted with F4).
- Over-budget history triggers summarization; recent K kept verbatim.
- Consolidated summary persists and is reused on the next run.
- Report flags are accurate; skips gracefully without DB.

## Acceptance Criteria

- [ ] Memory context respects a hard token budget.
- [ ] Older history is summarized, not dropped silently; recent stays verbatim.
- [ ] Consolidation reduces repeat cost; report flags are correct.
- [ ] Conventions + token tracking followed; UI meter renders.

## Open Questions

- Default budget value and "recent K verbatim" (propose budget 1500, K=2).
- Summarize per-entry or batch? Proposal: batch the overflow into one call.
