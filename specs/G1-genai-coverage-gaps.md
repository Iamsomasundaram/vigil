# G1 — GenAI Coverage Gaps and Proposed Tracks

- **Status:** Proposed (not approved, nothing built)
- **Axis:** Planning (what to add so the project covers a full GenAI developer + architect path)
- **Target:** none yet; this document is the input to future specs
- **Depends on:** completing the "original 8 findings" listed below first
- **Written:** 2026-11-25, after a review of the repository against a developer and an architect skill set

---

## Problem / Motivation

Vigil teaches agent patterns and reliability well. The question raised in review was
whether it covers enough to make a learner a solid GenAI **developer** and **architect**.
Answer: **not yet.** It is strong on "build and trust an agent" and thin on "run GenAI at
enterprise scale". This spec records the gaps so they can be prioritised after the current
clean-up work is finished.

> This is a gap analysis, not a commitment. Priorities and scope are to be revisited.

---

## What is already covered

- Prompting, structured output, chaining, parallel agents, routing, tool use (including MCP),
  memory, autonomous operation (L0 to L6, L4b).
- Four agent architectures (A1 to A4) and a LangGraph bridge for A1.
- Guardrails, evaluation, observability, resilience, cost control, drift, action governance,
  supply chain and release safety (R1 to R9).
- Tokenization, prompt lifecycle, model selection, fine-tuning decisions, factuality, privacy,
  responsible AI and semantic caching (F-series), plus one domain theme (T1).

---

## Developer gaps

| Gap | Today | What a developer should be able to do |
| --- | --- | --- |
| **Real retrieval (RAG)** | The "vector" score is a 64-bucket word hash and the built-in documents are tiny | Use a real embedding model, a vector store such as pgvector, real chunking, a reranker, and measure retrieval quality on a real corpus |
| **Production API habits** | Single synchronous-style calls | Stream responses, use batch APIs, use provider-side prompt caching, repair or retry malformed structured output, handle rate limits |
| **Evaluation depth** | A golden set and a judge exist (R2) | Calibrate LLM judges, run regression suites in CI, test non-deterministic output, track eval drift |
| **Agent frameworks and runtimes** | The LangGraph port is a one-node graph | Build a real multi-step graph, use durable workflows and queues, sandbox code execution, use agent-to-agent protocols |
| **Hands-on fine-tuning** | An advisor and a dataset validator only | Run a small training job and compare it with the base model |
| **Other modalities** | Images and PDFs (L4b) | Voice and realtime, computer use |

## Architect gaps

| Gap | What an architect should be able to do |
| --- | --- |
| **Deployment and platform** | Design scaling, multi-tenancy, identity and access, secrets handling and a model gateway with multi-provider fallback |
| **Enterprise data** | Design ingestion pipelines, freshness, and per-user access control inside retrieval |
| **Security and governance** | Threat-model an LLM system (for example against the OWASP LLM Top 10), plan red teaming, map to regulation (EU AI Act, GDPR, SOC 2). R1, R7 and F15 cover only part of this |
| **Business case** | Weigh build vs buy, total cost of ownership and vendor lock-in; set SLOs and plan capacity |
| **LLMOps** | CI/CD for prompts and evaluations, and a production observability stack |
| **Documentation habits** | Produce reference architectures and architecture decision records (ADRs) |
| **Model fundamentals** | Explain how transformers, inference and quantisation work at a primer level |

---

## Proposed tracks (suggested order, for later approval)

1. **Real RAG track** (highest value). pgvector, a real embedding model, chunking and
   reranking, evaluated with the existing F12 metrics on a real corpus.
2. **Architect's track.** Written reference architectures, ADRs, a threat model of Vigil
   itself, a compliance mapping, and a build-vs-buy / cost model template.
3. **Production API habits.** Streaming, batching, prompt caching, structured-output repair.
4. **Evaluation in CI.** Judge calibration and regression gates built on R2 and R9.
5. **Deployment reference.** Gateway, multi-tenancy and secrets, as a documented reference
   design rather than a full implementation.

Optional and lower priority: real fine-tuning run, voice/realtime, computer use, agent
protocols.

---

## Caveats

- Framework, model and regulation details change quickly. Before writing any content on
  specific frameworks, models, prices or regulations, verify against current sources.
- Keep the project focused. Adding every topic would dilute the learning path; prefer a few
  deep tracks over many shallow ones.

---

## Prerequisite: the original 8 findings

These come from the first repository review and are to be finished before this spec is
revisited.

| # | Finding | Status |
| --- | --- | --- |
| 1 | Clean-room install and test check | Done: fresh clone, no API key, passes (186 passed, 5 skipped) |
| 2 | Docker image build and `docker compose up` | Open |
| 3 | Ollama / local-model route verified | Open |
| 4 | Sample outputs and per-level cost from one real run | Open |
| 5 | Security defaults: mandatory API auth outside dev, CORS, request limits | Done: see F10 (VIGIL_ENV, scoped keys, CORS allow-list, request limits) |
| 6 | Split `vigil/api.py` and `ui/app.py` | Done: API into routers/schemas/hardening, UI into common + views/ (OpenAPI identical before and after) |
| 7 | Quality tooling: coverage report, type checking, stronger lint rules | Open |
| 8 | Housekeeping: line-ending renormalisation, CONTRIBUTING, changelog | Open |

---

## Acceptance Criteria (for this planning spec)

- [x] Gaps are written down with enough detail to turn into individual specs.
- [ ] Priorities and scope approved by the project owner.
- [ ] Each approved track gets its own spec before any code is written.
