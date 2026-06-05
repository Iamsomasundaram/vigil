# Vigil
### Autonomous CVE Intelligence & Remediation Agent
*A GenAI learning project — from a single LLM call to a fully autonomous security agent*

---

## What is Vigil?

Vigil solves a real problem: organisations are drowning in CVEs and don't know which ones actually matter to *their* environment, or what to do about them first.

More importantly, Vigil is a **learning project**. Each level introduces one new AI concept, building on the previous. By the time you reach Level 6, you will have built a genuinely autonomous AI agent from first principles.

---

## The Learning Path

| Level | File | Concept | What it does |
|-------|------|---------|--------------|
| L0 | `levels/l0_single_call.py` | Single LLM call | Explains a CVE in plain English |
| L1 | `levels/l1_chain.py` | Prompt chaining + structured output | 3-step chain: summarise → assess risk → remediation plan |
| L2 | `levels/l2_parallel.py` | Parallel agent fan-out | 4 specialist agents run simultaneously, moderator synthesises |
| L3 | `levels/l3_routing.py` | Conditional routing | System classifies CVE type, activates the right specialist track |
| L4 | `levels/l4_tools.py` | Real tool use | Queries NVD, EPSS, and your asset inventory |
| L5 | `levels/l5_memory.py` | Memory + feedback loops | Tracks remediation, follows up, learns from history |
| L6 | `levels/l6_autonomous.py` | Fully autonomous | Monitors CVE feeds, assigns tickets, verifies fixes — no human needed |

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
├── vigil/
│   ├── __init__.py       learning path overview
│   └── models.py         shared Pydantic schemas (used from L2+)
├── levels/
│   ├── l0_single_call.py  ← start here
│   ├── l1_chain.py
│   ├── l2_parallel.py
│   ├── l3_routing.py
│   ├── l4_tool_use.py
│   ├── l5_memory.py       requires PostgreSQL
│   └── l6_autonomous.py   requires PostgreSQL
├── data/
│   └── assets.json        sample asset inventory (used from L3+)
├── .env.example
└── pyproject.toml
```

---

## AI Concepts Covered

| Concept | Introduced at |
|---------|--------------|
| System prompts & personas | L0 |
| Temperature & model parameters | L0 |
| Structured output (Pydantic) | L1 |
| Prompt chaining | L1 |
| Context accumulation | L1 |
| `async`/`await` | L2 |
| `asyncio.gather()` — parallel execution | L2 |
| Multi-agent fan-out | L2 |
| Agent result aggregation | L2 |
| Conditional routing | L3 |
| Function / tool calling | L4 |
| External API integration (NVD, EPSS) | L4 |
| Persistent memory | L5 |
| Feedback loops | L5 |
| Autonomous goal-directed behaviour | L6 |
| Human-in-the-loop design | L6 |

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

The jump from L5 to L6 is where an AI *system* becomes an AI *agent*.

---

## Forking This Project

Vigil is intentionally kept simple for learning. Once you understand all 6 levels, fork it and build the enterprise version:
- Add a database (replace SQLite with PostgreSQL)
- Add a REST API (FastAPI)
- Add a frontend dashboard
- Connect to real SIEM/ticketing systems (Jira, ServiceNow, Splunk)
- Add multi-tenancy and auth
