# Vigil Progress Board

Last updated: 2026-08-31

## Done

- R1 — Guardrails & Prompt-Injection Defense
- R2 — Agent Evaluation & Regression Testing
- R3 — Observability & Tracing
- R4 — Resilience in the Agent Loop
- R5 — Cost Control & Budgeting
- E1 — Semantic Memory / RAG Extension
- E2 — Human-in-the-Loop Extension
- E3 — Agent Communication Topologies
- E4 — Model Inference Layer
- F1 — Real Embeddings & Vector RAG
- F2 — Multimodal Inputs
- F3 — Multi-Provider & Local Models
- F4 — Tokenization & Context Economics
- F5 — Context-Window Management
- F6 — Prompt Engineering Techniques
- F7 — Framework Bridge (LangGraph mapping + port)
- F8 — MCP Tool Server Path
- F9 — Learning Scaffolding
- F10 — Production Hardening (auth/rate/cache/faithfulness)
- F11 — Retrieval Data Preparation and Index Quality
- F12 — Retrieval Evaluation and Search Metrics
- F13 — Factuality, Hallucination, and Citation Verification
- F14 — Prompt Lifecycle, Versioning, and Experiments
- F15 — Privacy, Data Governance, and Safe Logging
- F16 — Hybrid Retrieval and Reranking
- F17 — Online Evaluation and Drift Monitoring
- F18 — Agent Permissions, Sandboxing, and Action Governance
- F19 — AI Supply Chain and Dependency Security
- F20 — Release Safety: Shadow, Canary, and Rollback
- F21 — Fine-tuning, Adapters, and Build-vs-Tune Decisions
- F22 — Claude Model Selection, Messages Bridge, and MCP Client
- F23 — Responsible-AI Evaluation (Moderation + Fairness)
- F24 — Semantic Caching
- T1 — Incident Response Ops Theme

## Pending Approved Ideas

None.

## Theme Track Status

- T1 — Incident Response Ops: Done
- Additional themes for this repo day: none (kept intentionally to complete one theme end-to-end)

## What Landed In The Final Batch

| Spec | Main code delivered                                                                           | Verification                       |
| ---- | --------------------------------------------------------------------------------------------- | ---------------------------------- |
| F4   | `levels/foundations/tokenization.py`, `/foundations/tokenize`, pricing context budget helpers | `tests/test_tokenization.py`       |
| F6   | `levels/foundations/prompting.py`, `/foundations/prompt-compare`, UI page                     | `tests/test_prompting.py`          |
| F7   | `architectures/frameworks/a1_react_langgraph.py`, mapping doc, `/frameworks/a1`               | `tests/test_frameworks.py`         |
| F8   | `vigil_mcp/vigil_server.py`, L4 tool discovery + `/l4/tools?source=...`                             | `tests/test_mcp.py`                |
| F10  | API hardening middleware, cache backend, faithfulness metric in R2                            | `tests/test_hardening.py`          |
| F11  | `levels/foundations/retrieval_quality.py`, `/foundations/retrieval-lab`, UI page              | `tests/test_retrieval_quality.py`  |
| F12  | Retrieval benchmark + metrics (`Recall@k`, `MRR`, `nDCG`), `/foundations/retrieval-eval`      | `tests/test_retrieval_eval.py`     |
| F13  | `levels/foundations/factuality.py`, `/foundations/factuality-check`, UI page                  | `tests/test_factuality.py`         |
| F14  | `levels/foundations/prompt_lifecycle.py`, prompt versions data, compare endpoints/UI          | `tests/test_prompt_lifecycle.py`   |
| F15  | `levels/foundations/privacy.py`, `/foundations/privacy/redact`, UI page                       | `tests/test_privacy.py`            |
| T1   | `levels/themes/incident_ops.py`, `/themes/incident/analyse`, UI theme track                   | `tests/test_theme_incident_ops.py` |

## Suite Status

- Full suite: **173 passed, 7 skipped**
