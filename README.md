# Vigil

### Autonomous CVE Intelligence & Remediation Agent

_A GenAI learning project — from a single LLM call to a fully autonomous security agent_

---

## What is Vigil?

Vigil solves a real problem: organisations are drowning in CVEs and don't know which ones actually matter to _their_ environment, or what to do about them first.

More importantly, Vigil is a **learning project**. Each level introduces one new AI concept, building on the previous. By the time you reach Level 6, you will have built a genuinely autonomous AI agent from first principles.

---

## Start Here (15 minutes)

New to Vigil? Follow this order. Steps 1–3 need no API key.

1. **Install** — create a virtual environment and `pip install -e ".[full,dev,foundations,notebooks]"` (see [Setup](#setup)).
2. **Check it works** — `python -m pytest -q`. Every test stubs the LLM, so this runs offline.
3. **Poke at concepts** — `jupyter lab notebooks/`, then open `00_setup.ipynb`. These run without a key.
4. **Add a key** — copy `.env.example` to `.env` and set `OPENAI_API_KEY` (or see [Run without OpenAI](#run-without-openai-free--local)).
5. **Run Level 0** — `python levels/l0_single_call.py CVE-2021-44228`, then read the file top to bottom.
6. **Continue L1 → L4**, doing the matching [exercise](exercises/README.md) after each level.
7. **Explore the UI** (optional) — see [Running the API and UI](#running-the-api-and-ui).

L5 and L6 need PostgreSQL, so start them only once L0–L4 are comfortable.

---

## The Learning Path

| Level | File                       | Concept                             | What it does                                                          |
| ----- | -------------------------- | ----------------------------------- | --------------------------------------------------------------------- |
| L0    | `levels/l0_single_call.py` | Single LLM call                     | Explains a CVE in plain English                                       |
| L1    | `levels/l1_chain.py`       | Prompt chaining + structured output | 3-step chain: summarise → assess risk → remediation plan              |
| L2    | `levels/l2_parallel.py`    | Parallel agent fan-out              | 4 specialist agents run simultaneously, moderator synthesises         |
| L3    | `levels/l3_routing.py`     | Conditional routing                 | System classifies CVE type, activates the right specialist track      |
| L4    | `levels/l4_tool_use.py`    | Real tool use                       | Queries NVD, EPSS, and your asset inventory                           |
| L5    | `levels/l5_memory.py`      | Memory + feedback loops             | Tracks remediation, follows up, learns from history                   |
| L6    | `levels/l6_autonomous.py`  | Fully autonomous                    | Monitors CVE feeds, assigns tickets, verifies fixes — no human needed |

> L4b (`levels/l4b_multimodal.py`) adds vision + PDF advisory parsing.

---

## Beyond the Levels

The levels are Axis 1 (capability). Three more axes build on them — each module has
a spec in [`specs/`](specs/README.md) and a live page in the Streamlit UI.

| Track                      | Range  | What it teaches                                                                                                                                                                                                                                                                   |
| -------------------------- | ------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Architectures**          | A1–A4  | ReAct, Plan-and-Execute, Reflection, Multi-Agent                                                                                                                                                                                                                                  |
| **Reliability & Safety**   | R1–R5  | Guardrails, evaluation, observability, resilience, cost control                                                                                                                                                                                                                   |
| **Axis Extensions**        | E1–E4  | Semantic memory, human-in-the-loop, agent comms, inference layer                                                                                                                                                                                                                  |
| **Foundations & Frontier** | F1–F24 | Embeddings/RAG, multimodal, tokenization, prompting, MCP, retrieval quality/metrics, factuality, prompt lifecycle, privacy, hybrid RAG + reranking, drift, action governance, supply chain, release safety, fine-tuning, Claude model selection, responsible-AI, semantic caching |
| **Theme Tracks**           | T1     | Domain portability — incident-response ops beyond CVEs                                                                                                                                                                                                                            |

Full index and status: [`specs/README.md`](specs/README.md) and
[`specs/progress-board.md`](specs/progress-board.md).

---

## Which Tracks Should I Do?

You do not need all of it. Pick a depth.

| Tier             | What to do                                                                 | Time      |
| ---------------- | -------------------------------------------------------------------------- | --------- |
| **Core**         | Levels L0–L4, the three exercises, notebooks 00–03                         | 1–2 days  |
| **Intermediate** | L5–L6, architectures A1–A4, reliability R1–R5, retrieval/RAG (F1, F11–F16) | 1 week    |
| **Advanced**     | R6–R9, governance and privacy (F15, F18–F20), fine-tuning (F21), MCP (F8), theme T1 | as needed |

Each track has a spec in [`specs/`](specs/README.md) that states the goal and what to build.
Time estimates are rough guides, not measured.

---

## Documentation

A beginner-friendly **guide** lives in [`docs/`](docs/index.html): plain-English explanations, diagrams,
real code walked through line by line, experiments and self-check questions. Open it locally, no server needed:

```bash
python docs/build_site.py      # rebuilds docs/index.html and docs/pages/*.html
```

Then open [`docs/index.html`](docs/index.html) in a browser. The guide is written in Markdown under `docs/src/`, and code snippets
are pulled straight from the source files, so they cannot drift. Levels L0–L2 are written so far; the generated
module/endpoint/spec reference is at [`docs/pages/reference.html`](docs/pages/reference.html).

---

## Interactive Learning

Prefer to learn by doing? Two hands-on tracks complement the levels above:

- **Notebooks** ([`notebooks/`](notebooks/README.md)) — runnable, offline-friendly
  notebooks where you change one parameter and watch the effect: tokenization,
  prompting, and embeddings/RAG. Start with `notebooks/00_setup.ipynb`.

  ```bash
  pip install -e ".[notebooks]"
  jupyter lab notebooks/
  ```

- **Exercises** ([`exercises/`](exercises/README.md)) — short "try it yourself"
  challenges with a stub to complete, a hidden reference solution, and a grader.

  ```bash
  pytest exercises/l0_prompting -q   # fails until you complete start.py
  ```

---

## Setup

```bash
# 1. Clone / navigate to the project
cd vigil

# 2. Create a virtual environment
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate

# 3. Install dependencies
#
#   L0–L4 (no database needed):
pip install -e .
#
#   L5–L6 + API server (requires PostgreSQL):
pip install -e ".[api]"
#
#   Streamlit UI only:
pip install -e ".[ui]"
#
#   Everything at once (recommended for exploring all levels):
pip install -e ".[full]"

#   Foundations modules (F4/F6):
pip install -e ".[foundations]"

#   Framework bridge (F7, optional):
pip install -e ".[frameworks]"

#   MCP tool server (F8, optional):
pip install -e ".[mcp]"

#   Claude Messages API bridge (optional):
pip install -e ".[claude]"

# 4. Set your API key
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY
```

---

## Running the API and UI

The FastAPI service wraps every level, and the Streamlit UI has one page per level.

**Option A — Docker Compose (needed for L5/L6, which use PostgreSQL and Redis):**

```bash
cp .env.example .env            # Windows PowerShell: Copy-Item .env.example .env
# edit .env and set OPENAI_API_KEY
docker compose up --build
```

| Service | URL                           |
| ------- | ----------------------------- |
| API     | http://localhost:8000/docs    |
| UI      | http://localhost:8501         |

Run the test suite inside the same image: `docker compose --profile test run --rm test`.

**Option B — locally, without Docker (L0–L4 pages only):**

```bash
pip install -e ".[full]"
uvicorn vigil.api:app --reload          # terminal 1
streamlit run ui/app.py                 # terminal 2
```

If you run the API locally, memory-backed endpoints (L5/L6) need `DATABASE_URL`
pointing at your own PostgreSQL. The default (`...@db:5432/vigil`) only resolves
inside Docker Compose.

---

## Cost and Offline Options

**What needs no key and no money:** the test suite, the notebooks (live-call cells are skipped), and the three exercises.

**What needs a key:** running the level scripts (L0–L6) against OpenAI. Each call is billed per token.
The repo's estimator ([`vigil/pricing.py`](vigil/pricing.py)) encodes these list prices per million tokens
(input / output): `gpt-4o-mini` $0.15 / $0.60 and `gpt-4o` $2.50 / $10.00. These figures are **indicative only**: they were copied into
the code at one point in time, provider prices change, and they are not updated automatically. Treat them as a rough guide and check OpenAI's pricing page for current rates. The default model is
`gpt-4o-mini`, the cheaper of the two. R5 (cost control) shows per-request token and cost estimates, so you
can measure what each level costs you rather than guessing.

### Run without OpenAI (free / local)

The level scripts use the OpenAI SDK, which honours the `OPENAI_BASE_URL` environment variable. Pointing it at
a local [Ollama](https://ollama.com) server should let L0–L4 run on your own machine:

```bash
ollama pull llama3.1:8b
# in .env
OPENAI_BASE_URL=http://localhost:11434/v1
OPENAI_API_KEY=ollama          # any non-empty value
OPENAI_MODEL=llama3.1:8b
```

This route has not been verified against every level. Smaller local models follow structured-output and
tool-calling instructions less reliably, so L1 and L4 may fail or give weaker answers. The API's multi-provider
layer (F3 / E4, `vigil/inference.py`) supports Ollama and OpenAI-compatible endpoints directly.

Embeddings are offline by default (`VIGIL_EMBED_MODE=local`), so L5 memory recall needs no embedding API.

---

## Running Each Level

Levels L0–L4 are independently runnable with just `pip install -e .`.
L5 and L6 require PostgreSQL — use Docker Compose (see [Running the API and UI](#running-the-api-and-ui)) or supply your
own `DATABASE_URL`.

```bash
# Level 0 — single LLM call  (requires: base install)
python levels/l0_single_call.py CVE-2021-44228

# Level 1 — chained prompts + structured output  (requires: base install)
python levels/l1_chain.py CVE-2021-44228

# Level 2 — parallel agents + moderator  (requires: base install)
python levels/l2_parallel.py CVE-2021-44228

# Level 3 — routing  (requires: base install)
python levels/l3_routing.py CVE-2021-44228

# Level 4 — tool use  (requires: base install)
python levels/l4_tool_use.py CVE-2021-44228

# Level 5 — memory  (requires: pip install -e ".[api]" + running PostgreSQL)
python levels/l5_memory.py CVE-2021-44228

# Level 6 — autonomous monitor  (requires: pip install -e ".[api]" + running PostgreSQL)
python levels/l6_autonomous.py --scan CVE-2021-44228
```

### What you should see

Model text differs on every run, so compare the *shape* of the output, not the wording.

| Level | Command prints                                                                                                   | Sanity check                                                      |
| ----- | ---------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------- |
| L0    | A `VIGIL — Level 0` header with the model and CVE, then one panel titled with the CVE ID                         | The panel answers the five numbered questions in the prompt       |
| L1    | Three stages in order: CVE summary, risk assessment, remediation plan                                            | Each stage reuses facts from the one before                       |
| L2    | One card per specialist agent, then a moderator's final verdict                                                  | Wall time is about one agent's latency, not four added together   |
| L3    | A routing decision first, then the result of one of four tracks: critical, standard patch, low risk, human review | A famous critical CVE should not land in the low-risk track       |
| L4    | The same analysis, grounded in live NVD and EPSS lookups and your asset inventory in `data/assets.json`          | The scores shown match what NVD and EPSS return today             |
| L5–L6 | Memory and autonomous-monitor output backed by PostgreSQL                                                        | A second run for the same CVE can draw on the first               |

Token usage per run is available through each level's `get_usage()`. Each level's module docstring explains what it should do and why.

Try different CVEs to see how the outputs vary:

- `CVE-2021-44228` — Log4Shell (critical, widely known)
- `CVE-2023-44487` — HTTP/2 Rapid Reset (DDoS)
- `CVE-2022-22965` — Spring4Shell (RCE)

---

## Troubleshooting

| Symptom                                                         | Likely cause and fix                                                                                         |
| --------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------ |
| `The api_key client option must be set...` when running a level | No key loaded. Create `.env` from `.env.example`, set `OPENAI_API_KEY`, and run from the repo root.          |
| `ModuleNotFoundError: vigil` / `levels` / `reliability`         | Package not installed. Activate the venv and run `pip install -e .` (or an extra) from the repo root.        |
| `ModuleNotFoundError: pytest`                                   | Dev extra missing: `pip install -e ".[dev]"`.                                                                |
| PowerShell blocks `.venv\Scripts\Activate.ps1`                  | Run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, or call `.venv\Scripts\python.exe` directly.      |
| `python` opens the Microsoft Store (Windows)                    | Install Python 3.11+ and disable the "App execution aliases" for python in Windows Settings.                 |
| L5/L6 fail to connect to the database                           | PostgreSQL isn't running, or `DATABASE_URL` still points at host `db`. Use Docker Compose or set your own URL. |
| Streamlit pages show connection errors                          | The API isn't running. Start it, or set `VIGIL_API_URL` if it isn't on `localhost:8000`.                      |
| `401` from the API                                              | `VIGIL_API_KEYS` is set in `.env`. Send a matching key, or leave the variable empty for local use.           |
| L4 returns no NVD or EPSS data                                  | Those are live public APIs. Check your network connection and retry, since they can rate-limit or time out.  |
| Tests are slow or fail on optional features                     | Install the extras CI uses: `pip install -e ".[full,dev,foundations]"`. Skipped tests mean an extra is absent. |

Still stuck? Run `python -m pytest -q` first. If it fails on a clean checkout, that is a repo bug worth reporting.

---

## Project Structure

```
vigil/
├── vigil/            API, shared models, inference seam, pricing, cache, Claude bridge
├── levels/           L0–L6 capability levels
│   ├── foundations/  F-series modules (tokenization, retrieval, factuality, …)
│   └── themes/       T-series domain tracks (incident ops)
├── architectures/    A1–A4 orchestration patterns (+ frameworks/ bridge)
├── reliability/      R1–R9: guardrails, eval, observability, resilience, cost, drift, governance, supply chain, release safety
├── vigil_mcp/        MCP tool server + client path (see vigil_mcp/README.md)
├── ui/               Streamlit learning UI
├── specs/            One spec per feature + progress board
├── tests/            Full pytest suite
├── docs/             Beginner guide (Markdown in docs/src) + generated reference
├── notebooks/        Interactive, offline-friendly notebooks
├── exercises/        Graded "try it yourself" challenges
├── data/             Sample assets, eval sets, manifests
└── pyproject.toml
```

---

## AI Concepts Covered

| Concept                                 | Introduced at |
| --------------------------------------- | ------------- |
| System prompts & personas               | L0            |
| Temperature & model parameters          | L0            |
| Structured output (Pydantic)            | L1            |
| Prompt chaining                         | L1            |
| Context accumulation                    | L1            |
| `async`/`await`                         | L2            |
| `asyncio.gather()` — parallel execution | L2            |
| Multi-agent fan-out                     | L2            |
| Agent result aggregation                | L2            |
| Conditional routing                     | L3            |
| Function / tool calling                 | L4            |
| External API integration (NVD, EPSS)    | L4            |
| Persistent memory                       | L5            |
| Feedback loops                          | L5            |
| Autonomous goal-directed behaviour      | L6            |
| Human-in-the-loop design                | L6            |

---

## The Agency Spectrum

```
L0  ──  Single call      "What is this CVE?"
L1  ──  Chain            Explain → Assess → Plan
L2  ──  Parallel         4 agents analyse simultaneously
L3  ──  Routing          System decides which agents to call
L4  ──  Tools            Agents use real APIs and data
L5  ──  Memory           Tracks, loops, follows up
L6  ──  Autonomous       Sets its own goals, acts without prompting
```

The jump from L5 to L6 is where an AI _system_ becomes an AI _agent_.

---

## Forking This Project

Vigil is a teaching codebase. PostgreSQL memory, a FastAPI service, a Streamlit UI and optional API-key auth already exist. To take it towards production, fork it and add what is still missing:

- Connect to real SIEM/ticketing systems (Jira, ServiceNow, Splunk)
- Make API authentication mandatory (it is optional today) and add multi-tenancy
- Add database migrations and managed secrets
- Split `vigil/api.py` and `ui/app.py` into routers and per-page modules
