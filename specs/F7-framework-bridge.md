# F7 — Framework Bridge: LangGraph / LlamaIndex / CrewAI

- **Status:** Draft
- **Axis:** Foundations (GenAI literacy) — ecosystem mapping
- **New module:** `architectures/frameworks/`
- **Depends on:** A1–A4 (hand-rolled orchestration), L4 (tools)

---

## Problem / Motivation

Vigil builds every pattern by hand — excellent for fundamentals — but a learner finishes
without ever seeing how their patterns map to the frameworks they'll use at work
(LangGraph, LlamaIndex, CrewAI, AutoGen, OpenAI Agents SDK). The frameworks are only
name-dropped in a comment in `a4_multi_agent.py`. F7 builds **one** familiar Vigil
pattern in **one** framework so the mental model transfers.

## Teaching Goal

**A learner re-implements an existing Vigil architecture (e.g. A1 ReAct or A4
multi-agent) in LangGraph and sees the 1:1 mapping** — nodes ↔ functions, edges ↔
control flow, state ↔ the messages/dict they already manage by hand. They learn what
frameworks add (graph runtime, checkpointing, streaming) and what they hide.

## Goals

- **One faithful port** — `architectures/frameworks/a1_react_langgraph.py` reproducing
  A1's behavior using LangGraph, same CVE task and structured output.
- **Mapping doc** — inline table: Vigil concept → LangGraph concept (and notes for
  CrewAI / LlamaIndex / OpenAI Agents SDK).
- **Optional second port** — `a4_multi_agent_crewai.py` (stretch) to contrast topologies.
- **Isolation** — frameworks live behind an extra so the core project stays dependency-light.

## Non-Goals

- Adopting a framework as the project default (the hand-rolled versions remain canonical).
- Covering every framework deeply — depth in one, pointers for the rest.

## Design

```
A1 (hand-rolled ReAct)            LangGraph port
  while loop + tool dispatch  ⇄   StateGraph(nodes=[reason, act], edges=conditional)
  messages list               ⇄   graph state (TypedDict)
  max_iterations              ⇄   recursion_limit
```

## Proposed Files

- **New** `architectures/frameworks/__init__.py`.
- **New** `architectures/frameworks/a1_react_langgraph.py` — CLI-runnable, same output.
- **New** `architectures/frameworks/MAPPING.md` — concept mapping table.
- **Edit** `pyproject.toml` — extra `frameworks = ["langgraph>=0.2", "langchain-openai>=0.2"]`.
- **New** `tests/test_frameworks.py` — graph compiles; one run produces a valid verdict
  (LLM stubbed). Skips if `langgraph` not installed.
- **Edit** `ui/app.py` — an "A1 vs LangGraph" comparison note on the A1 page.

## Data Models

Reuse existing A1 output models; no new schema required.

## API & CLI Surface

- CLI: `python -m architectures.frameworks.a1_react_langgraph CVE-2021-44228`.
- Optional `POST /frameworks/a1` mirroring the existing A1 endpoint for parity demos.

## Tests (`tests/test_frameworks.py`)

- LangGraph graph builds and runs end-to-end with a stubbed model.
- Output validates against the same A1 Pydantic model.
- Skips gracefully when the `frameworks` extra is absent.

## Acceptance Criteria

- [ ] A1 ReAct reproduced in LangGraph with equivalent output.
- [ ] Mapping doc explains node/edge/state correspondence.
- [ ] Framework deps isolated behind an extra; tests skip without it.

## Open Questions

- Port A1 (simplest, clearest) or A4 (shows multi-agent value)? Proposal: A1 first, A4 stretch.
