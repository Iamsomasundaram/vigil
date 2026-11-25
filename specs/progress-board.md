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

## Proposed (not approved)

- G1 — GenAI Coverage Gaps and Proposed Tracks ([spec](G1-genai-coverage-gaps.md)). Planning only; to be revisited after the original review findings are closed.

## Review Findings Tracker

| #   | Finding                                                         | Status |
| --- | --------------------------------------------------------------- | ------ |
| 1   | Clean-room install and test check                               | Done   |
| 2   | Docker image build and `docker compose up`                      | Open   |
| 3   | Ollama / local-model route verified                             | Open   |
| 4   | Sample outputs and per-level cost from one real run             | Open   |
| 5   | Security defaults (mandatory auth outside dev, CORS, limits)    | Done   |
| 6   | Split `vigil/api.py` and `ui/app.py`                            | Done   |
| 7   | Quality tooling (coverage, type checking, stronger lint)        | Open   |
| 8   | Housekeeping (line endings, CONTRIBUTING, changelog)            | Open   |

### Open items in detail

**#2 Docker image build and `docker compose up`** (next up; needs the user's go-ahead before running, it pulls and starts images)
- Build the API and UI images; confirm `architectures/` and `vigil_mcp/` are in the API image (Dockerfile was edited, never built).
- Verify the compose security pass-through added in finding #5 (`VIGIL_ENV`, `VIGIL_API_KEYS`, `VIGIL_CORS_ORIGINS`, `VIGIL_UI_API_KEY`) works end to end: UI to API with a key set, `prod` refusing to start without keys.
- Bind Postgres (5432) and Redis (6379) to `127.0.0.1` in `docker-compose.yml`.
- Confirm L5/L6 work against the compose database.

**#3 Ollama / local-model route**
- The README "Cost and Offline Options" route is unverified. Run one level against a local Ollama model and record what works.
- Confirm whether `VIGIL_TOOL_SOURCE=mcp` really uses MCP or silently falls back to inline.

**#4 Sample outputs and per-level cost from one real run** (needs the user's OpenAI key)
- Capture real output and the estimated cost for each level, and add them to the docs so learners can compare.

**#7 Quality tooling**
- Coverage report, type checking (mypy or pyright), and lint rules beyond the current F-rules only.

**#8 Housekeeping**
- Renormalise line endings (repo has mixed LF/CRLF; `.gitattributes` is in place), add CONTRIBUTING and a changelog.

### Known gaps to fold into the items above

| Gap | Where | Fold into |
| --- | --- | --- |
| R4's 0.1 s timeout vs live services is untested | `reliability/r4_resilience.py` | #3 / #4 (real run) |
| R3 span parenting under concurrency is untested | `reliability/r3_observability.py` | #7 (tests) |
| Privacy redaction misses names and addresses (documented) | `levels/foundations/privacy.py` | G1 |
| Semantic cache is word-overlap, not embeddings (documented) | `levels/foundations/semantic_cache.py` | G1 (real RAG track) |
| L6: an EPSS fetch failure on a CVE's first scan records 0.0 | `levels/l6_autonomous.py` | #4 |
| Mobile layout of the docs site unconfirmed on a real phone | `docs/assets/style.css` | #8 |
| Security: rate limit and concurrency cap are per process; keys have no expiry or revocation; OIDC only documented | `vigil/hardening.py` | G1 (deployment reference) |
| Leftover clean-room folders `D:\vigil-cr`, `D:\vigil-cr-log.txt` | outside the repo | user to delete |

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
