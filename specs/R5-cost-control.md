# R5 — Cost Control & Token Economics

- **Status:** Draft
- **Axis:** 3 — Reliability & Safety
- **Module:** `reliability/r5_cost_control.py`
- **Depends on:** L0+ (token tracking already exists everywhere); pairs with E4 (model routing)
- **Checklist:** §6 Token Economics (Token Monitoring, Prompt Optimization, Response Caching, Cost Attribution, Context Budgeting)

---

## Problem / Motivation

Every level already computes per-run cost, but there is no **control**: no budget
caps, no caching of repeated calls, no per-feature cost attribution, and no context
budgeting. An autonomous L6 monitor scanning a large watchlist on a short interval
can silently run up a bill. Cost is a first-class production concern.

## Teaching Goal

**A learner sets a budget, enables caching, and watches repeated/over-budget runs be
short-circuited** — then reads a cost-attribution report showing where the money
went (per level, per CVE, per model). They learn that token economics is an
engineering discipline, not an afterthought.

## Goals

- **Budget enforcement** — a `BudgetGuard` with per-request and per-session USD caps;
  raises/halts (with a clean partial result) when exceeded; supports a soft warn
  threshold.
- **Response caching** — content-addressed cache keyed on (model, system, user,
  tools) hash; in-memory by default, optional Redis. Cache hits cost $0 and are
  attributed as such.
- **Cost attribution** — tag every LLM call with `feature` and `cve_id`; aggregate
  into a report (group by level/CVE/model).
- **Context budgeting** — a helper that trims/summarizes accumulated context (e.g.
  long L1 chains, L5 memory injection) to stay under a token ceiling before the call.
- A `--report` mode rendering a `rich` table of spend by dimension.

## Non-Goals

- Real billing integration or quota provisioning.
- Model selection logic itself — that lives in E4; R5 _consumes_ E4 to price routes.

## Design

```
request ─► BudgetGuard.check(estimate)
              │ over cap → halt / return partial
              ▼
         cache.get(key)  ── hit ─► return cached ($0, attributed "cache")
              │ miss
              ▼
        context_budget.fit(messages, ceiling)
              ▼
           llm.call ─► _track() + attribute(feature, cve_id, model)
              ▼
         cache.put(key, result)
```

Wraps the existing `_track` mechanism; attribution writes to a `CostLedger` that the
report reads.

## Proposed Files

- **New** `reliability/r5_cost_control.py` — `BudgetGuard`, `cache`, `CostLedger`,
  `fit_context`, `--report`.
- **Edit** `vigil/models.py` — `CostEntry`, `CostReport`, `BudgetStatus`.
- **Edit** `vigil/api.py` — `GET /r5/report`, `POST /r5/budget` (set caps).
- **Edit** `pyproject.toml` — optional `redis` dependency under a `cache`/`api` extra.
- **New** `tests/test_cost_control.py`.

## Data Models (`vigil/models.py`)

```python
class CostEntry(_Base):
    feature: str          # "l2", "r1", ...
    cve_id: str | None
    model: str
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float
    cache_hit: bool

class BudgetStatus(_Base):
    limit_usd: float
    spent_usd: float
    remaining_usd: float
    exceeded: bool

class CostReport(_Base):
    entries: list[CostEntry]
    total_usd: float
    by_feature: dict[str, float]
    by_model: dict[str, float]
    cache_savings_usd: float
```

## API & CLI Surface

- `POST /r5/budget` — `{request_cap_usd, session_cap_usd, warn_ratio}` → `BudgetStatus`.
- `GET /r5/report` — `CostReport`.
- CLI: `python reliability/r5_cost_control.py CVE-2021-44228 --budget 0.01`
- CLI: `python reliability/r5_cost_control.py --report`

## Tests (`tests/test_cost_control.py`)

- Budget guard halts when an estimate exceeds the cap; soft warn fires at threshold.
- Identical request hits cache; second call records `cache_hit=True`, $0 cost.
- Attribution groups correctly by feature/model; `cache_savings_usd` computed.
- `fit_context` trims oversized message history below the ceiling.

## Acceptance Criteria

- [ ] Over-budget run is short-circuited with a clean partial result, not a crash.
- [ ] Cache hit demonstrably costs $0 and is reflected in the report.
- [ ] Report attributes spend by feature, CVE, and model.
- [ ] Conventions followed; tests use stubs, no real calls.

## Open Questions

- Pricing table currently hardcoded per file. Proposal: centralize a
  `vigil/pricing.py` map keyed by model (also used by E4) — minor refactor.
- Cache invalidation for live data (NVD/EPSS change daily). Proposal: TTL on tool
  results, no TTL on pure-LLM transforms.
