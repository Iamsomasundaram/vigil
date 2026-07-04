# Vigil Specs — Spec-Driven Development

This directory contains design specs for extending Vigil. We use **spec-driven
development**: every new module is described here _before_ it is built, reviewed,
then implemented one spec at a time. Each spec is self-contained and actionable.

---

## The Three Axes

Vigil teaches agentic AI along three orthogonal axes. The first two exist; the
third is what these specs introduce.

```
Axis 1 — Capability        (levels/    L0–L6):  WHAT the agent can do
Axis 2 — Orchestration     (architectures/ A1–A4): HOW reasoning is structured
Axis 3 — Reliability & Safety (reliability/ R1–R5): HOW you TRUST it in production   ← NEW
Axis 4 — Foundations & Frontier (F1–F10):  the GenAI literacy the other axes assume   ← NEW
```

Axis 3 covers the cross-cutting concerns described (as theory) in
[`agentic_ai_production_readiness_checklist.md`](../agentic_ai_production_readiness_checklist.md).
These specs turn that checklist into runnable, teachable modules.

Axis 4 closes the GenAI-literacy gaps the existing axes assume but never teach
directly: real embeddings/RAG, multimodal input, local/open models, tokenization,
context-window management, prompt-engineering technique, framework mapping, MCP,
interactive notebooks, and production hardening.

In addition, several specs **extend the existing axes** where the current
implementation stops short of production patterns.

---

## Spec Index

### Axis 3 — Reliability & Safety (new `reliability/` modules)

| Spec                      | Module                            | Concept                                            | Checklist §        | Depends on |
| ------------------------- | --------------------------------- | -------------------------------------------------- | ------------------ | ---------- |
| [R1](R1-guardrails.md)    | `reliability/r1_guardrails.py`    | Prompt-injection defense & I/O guardrails          | §3 Guardrails      | L4         |
| [R2](R2-evaluation.md)    | `reliability/r2_evaluation.py`    | Agent evals: golden sets, LLM-as-judge, regression | §8 Evaluation      | L1–L4      |
| [R3](R3-observability.md) | `reliability/r3_observability.py` | Structured tracing & span attribution              | §7 Observability   | L4         |
| [R4](R4-resilience.md)    | `reliability/r4_resilience.py`    | Retries, timeouts, circuit breakers, degradation   | §2 Fallbacks       | L4, L6     |
| [R5](R5-cost-control.md)  | `reliability/r5_cost_control.py`  | Token budgets, caching, cost attribution           | §6 Token Economics | L0+        |

### Axis extensions (modify existing levels/architectures)

| Spec                              | Extends                               | Concept                                     |
| --------------------------------- | ------------------------------------- | ------------------------------------------- |
| [E1](E1-semantic-memory.md)       | L5 `levels/l5_memory.py`              | Semantic memory / RAG over past CVEs        |
| [E2](E2-human-in-the-loop.md)     | A2 `architectures/a2_plan_execute.py` | Real human-in-the-loop approval gates       |
| [E3](E3-agent-communication.md)   | A4 `architectures/a4_multi_agent.py`  | Agent-to-agent handoffs, debate, blackboard |
| [E4](E4-model-inference-layer.md) | shared `vigil/`                       | Model routing, fallback chains, streaming   |

### Axis 4 — Foundations & Frontier (GenAI literacy gaps)

| Spec                                    | Module / Target                      | Concept                                              | Priority |
| --------------------------------------- | ------------------------------------ | ---------------------------------------------------- | -------- |
| [F1](F1-real-embeddings-rag.md)         | `levels/l5_memory.py` (fix E1)       | Real embeddings + vector RAG (replaces fake hashing) | **1**    |
| [F2](F2-multimodal.md)                  | `levels/l4b_multimodal.py`           | Vision + PDF/document parsing                        | **2**    |
| [F3](F3-multi-provider-local-models.md) | `vigil/inference.py` (extends E4)    | Multi-provider + local/open models (Ollama)          | **3**    |
| [F4](F4-tokenization.md)                | `levels/foundations/tokenization.py` | Tokenization & context economics (`tiktoken`)        |          |
| [F5](F5-context-window-management.md)   | `levels/l5_memory.py` (extends L5)   | Context-window mgmt: summarize/truncate/compact      | **4**    |
| [F6](F6-prompt-engineering.md)          | `levels/foundations/prompting.py`    | Prompt techniques: zero/few-shot, CoT, templates     |          |
| [F7](F7-framework-bridge.md)            | `architectures/frameworks/`          | Framework bridge: LangGraph / CrewAI / LlamaIndex    |          |
| [F8](F8-mcp-tool-servers.md)            | `mcp/vigil_server.py`                | Model Context Protocol (MCP) tool servers            |          |
| [F9](F9-learning-scaffolding.md)        | `notebooks/`, `exercises/`           | Interactive notebooks + graded exercises             | **5**    |
| [F10](F10-production-hardening.md)      | `vigil/api.py`, R2/R5                | Auth, rate limiting, caching, faithfulness eval      |          |

---

## Recommended Implementation Order

1. **R1 Guardrails** — highest value; a security agent that ingests untrusted CVE
   text must defend against prompt injection first.
2. **R2 Evaluation** — needed to safely change anything else without regressions.
3. **R3 Observability** — makes every later spec debuggable.
4. **E4 Model/Inference layer** — unlocks cost control and resilience cleanly.
5. **R5 Cost Control**, **R4 Resilience** — build on E4.
6. **E1 / E2 / E3** — axis extensions, in any order.

## Axis 4 Priority (Foundations)

The GenAI-literacy gaps, in priority order:

1. **F1 Real Embeddings & Vector RAG** — fixes the one simulated concept (E1's fake
   embedding); foundational for all retrieval work. ← _implemented_
2. **F2 Multimodal** — adds the missing input modality (vision + documents). ← _implemented_
3. **F3 Multi-Provider & Local Models** — hosted vs local trade-offs via the E4 seam. ← _implemented_
4. **F5 Context-Window Management** — the production failure mode L5 currently ignores. ← _implemented_
5. **F9 Learning Scaffolding** — notebooks + exercises so learners experiment, not just read. ← _implemented_

F4, F6, F7, F8, F10 follow once the above land.

---

## Spec Template

Every spec follows this structure so they are easy to review and implement:

1. **Status** — Draft / Approved / In Progress / Done
2. **Axis & Dependencies** — where it fits, what must exist first
3. **Problem / Motivation** — the gap being closed
4. **Teaching Goal** — the one concept a learner takes away (this is a learning project)
5. **Goals / Non-Goals** — scope boundaries
6. **Design** — the approach, with diagrams where useful
7. **Proposed Files** — new/changed files, matching repo conventions
8. **Data Models** — additions to `vigil/models.py`
9. **API & CLI Surface** — endpoints and `python ...` entry points
10. **Tests** — what `tests/` must cover
11. **Acceptance Criteria** — checklist that defines "done"
12. **Open Questions**

---

## Conventions every implementation must follow

These mirror the existing levels/architectures so new modules feel native:

- **Header banner** — the box-drawing `╔══╗` comment block with CONCEPTS COVERED / WHY sections.
- **Token tracking** — module-level `_usage` dict, `_reset_usage()`, `_track(response)`, `get_usage()`.
- **Model selection** — `MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")`.
- **Config via env** — `.env` loaded with `python-dotenv`; never hardcode secrets.
- **Rich output** — use `rich.console.Console` for CLI rendering.
- **CLI entry** — `python reliability/rN_xxx.py CVE-2021-44228` runnable standalone.
- **Structured output** — Pydantic models in `vigil/models.py` with strict JSON schema.
- **API** — expose via FastAPI in `vigil/api.py` with `TokenUsage` in the response.
- **Tests** — async pytest, stub OpenAI + external APIs, skip gracefully if DB down.
- **pyproject extras** — add new optional dependencies under a named extra, not the base.
