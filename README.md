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

## Documentation

A browsable, self-contained HTML reference (structure, key modules & functions,
all API endpoints, and the spec index) is generated from the code:

```bash
python docs/build_docs.py     # regenerates docs/index.html
```

Open [`docs/index.html`](docs/index.html) in a browser.

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

## Running Each Level

Levels L0–L4 are independently runnable with just `pip install -e .`.
L5 and L6 require PostgreSQL — use Docker Compose (see below) or supply your
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

Try different CVEs to see how the outputs vary:

- `CVE-2021-44228` — Log4Shell (critical, widely known)
- `CVE-2023-44487` — HTTP/2 Rapid Reset (DDoS)
- `CVE-2022-22965` — Spring4Shell (RCE)

---

## Project Structure

```
vigil/
├── vigil/            API, shared models, inference seam, pricing, cache, Claude bridge
├── levels/           L0–L6 capability levels
│   ├── foundations/  F-series modules (tokenization, retrieval, factuality, …)
│   └── themes/       T-series domain tracks (incident ops)
├── architectures/    A1–A4 orchestration patterns (+ frameworks/ bridge)
├── reliability/      R1–R5 + governance/ops modules (drift, supply chain, …)
├── vigil_mcp/        MCP tool server + client path (see vigil_mcp/README.md)
├── ui/               Streamlit learning UI
├── specs/            One spec per feature + progress board
├── tests/            Full pytest suite
├── docs/             HTML documentation generator + output
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

Vigil is intentionally kept simple for learning. Once you understand all 6 levels, fork it and build the enterprise version:

- Add a database (replace SQLite with PostgreSQL)
- Add a REST API (FastAPI)
- Add a frontend dashboard
- Connect to real SIEM/ticketing systems (Jira, ServiceNow, Splunk)
- Add multi-tenancy and auth
