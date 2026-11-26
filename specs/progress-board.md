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

### P1 — Autonomous Tester capstone project ([spec](P1-autonomous-tester.md))

Approved by the owner on 2026-11-26. Codex SDK only, with our own orchestration where Codex has
no native capability. The agent is live (real model calls); mocks are used only in unit tests.
The bundled demo shop with seeded bugs is the only target. Generic by rule: no client names,
systems or counts. A realistic use case from the owner's own experience will be added later.

| Phase | Deliverable | Status |
| ----- | ----------- | ------ |
| P1.1 | Demo shop, seeded bugs, answer key, scorer, offline tests | Done |
| P1.2 | Scope contract, heuristics v1, observation-only scan (adds Playwright) | Not started |
| P1.3 | Validation strategy, classifier with confidence, re-triage, review queue, first live evaluation | Not started |
| P1.4 | Codex integration, guard, agency modes, audit (verify Codex auth and capabilities first) | Not started |
| P1.5 | Guide section, UI page, API route, README links | Not started |

## Proposed (not approved)

- G1 — GenAI Coverage Gaps and Proposed Tracks ([spec](G1-genai-coverage-gaps.md)). Planning only; to be revisited after the original review findings are closed.

## Review Findings Tracker

| #   | Finding                                                         | Status |
| --- | --------------------------------------------------------------- | ------ |
| 1   | Clean-room install and test check                               | Done   |
| 2   | Docker image build and `docker compose up`                      | Done   |
| 3   | Ollama / local-model route verified                             | Open   |
| 4   | Sample outputs and per-level cost from one real run             | Open   |
| 5   | Security defaults (mandatory auth outside dev, CORS, limits)    | Done   |
| 6   | Split `vigil/api.py` and `ui/app.py`                            | Done   |
| 7   | Quality tooling (coverage, type checking, stronger lint)        | Open   |
| 8   | Housekeeping (line endings, CONTRIBUTING, changelog)            | Open   |

### Open items in detail

**#2 Docker image build and `docker compose up`** (Done 2026-11-26, Docker Desktop 28.1.1, Compose v2.35.1)
- Built: `vigil-api` 328 MB, `vigil-ui` 845 MB, and the profile-gated `vigil-test` image. API image contains `architectures/`, `reliability/` and `vigil_mcp/`.
- `docker compose up --wait`: db, redis, api and ui all healthy. All four published ports bind to `127.0.0.1`.
- Verified: API endpoints that need no model respond; L5/L6 round trip through compose Postgres (tables exist, watchlist row written, read and deleted); malformed CVE id returns 422; dev mode logs the "API is OPEN" warning.
- Security pass-through verified in the containers: `VIGIL_ENV=prod` without keys exits with the clear error; with scoped keys the API returns 401 without a key, 403 for a run key on the kill switch, 200 for an admin key; the UI container sends `VIGIL_UI_API_KEY` and the API accepts it; CORS allows the Streamlit origin and rejects another.
- Test service: found it ran a stale image and lacked `docs/`, `exercises/`, `notebooks/`, `projects/` and `reliability/`; fixed the mounts and the docs copy. Whole suite passes in Docker: 301 passed, 3 skipped.
- Not verified: any call that uses a paid model (no model calls were made); the Streamlit pages beyond the health and index responses (the UI renders over a websocket, so curl cannot exercise it); `prod` default for CORS (Compose supplies the Streamlit origin as a default, now commented).
- Known: the UI image is 845 MB (Streamlit and its dependencies); not optimised. Fixed container names (`vigil-api`, ...) can clash with other projects.

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

### Stack and UI updates (2026-11-26)

- UI completeness check found two features with an API but no page: **R5 Cost Control** and **F8 Tool Discovery & MCP**; both pages added. Sidebar regrouped to mirror the guide (Start, Levels, Architectures, Reliability R1 to R9, Foundations, Extensions, Themes, Projects); R6 to R9 now carry their guide names alongside F17 to F20.
- Every page links to its guide page; the sidebar links the guide pages that have no UI page. A test keeps navigation, page registry, guide pages and rendering in step.
- Docker Compose now also runs the learning guide (`docs`, port 8090) and the demo shop (`demo-shop`, port 8100), both localhost-only.
- Finding for #3: the MCP "client" in `vigil_mcp/` runs in-process and calls the tool functions directly; it is not a separate MCP server process. The F8 page says so.
- Still without a dedicated UI page: F1 (embeddings), F5 (context window), F9 (learning scaffolding), F10 (hardening; see the guide's API security page) and the `/admin/ratelimit` diagnostic. Their topics are covered in the guide and, for F1/F5, inside the L5 page.

### P1 follow-ups carried forward (action items, do not lose)

| # | Follow-up | Must be handled in |
| --- | --- | --- |
| F1 | Exploratory matching in the scorer is plain term matching, a deterministic baseline. Back it with, or replace it by, a semantic judge once the live tester exists, and report both so the baseline stays comparable | P1.3 |
| F2 | A01 (renamed markup) only applies when scripts written for the version 1 markup run against version 2. The live run for `v2_markup` must execute stale v1 scripts first, then show repair; a freshly generated v2 script passes and does not test A01 | P1.4 |
| F3 | Every verdict except "skipped" must carry an evidence reference (the schema rejects it otherwise, including for passes). The tester must emit one for every verdict | P1.3, P1.4 |
| F4 | The answer key (`evals/seeded_bugs.yaml`) and the scorer must never be visible to the tester. The Codex workspace must be a generated folder that contains neither, and no `.env` | P1.4 (isolation) |
| F5 | Set a per-run and per-evaluation cost ceiling, and show an estimate, before the first live run | P1.3 |
| F6 | Verify Codex auth, billing behaviour (`OPENAI_API_KEY` vs `CODEX_API_KEY`), Python vs TypeScript SDK, hooks, subagents, MCP, usage events and spend limits against the installed version | Before P1.4 |
| F7 | A new top-level package (`projects`) is not picked up by an existing editable install; re-run `pip install -e ".[tester]"` after pulling | README / P1.5 docs |
| F8 | Add a realistic use case from the owner's own testing experience (generic, no client specifics) | Owner to supply, after P1.2 |

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
