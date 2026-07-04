# E4 — Model / Inference Layer (shared)

- **Status:** Draft
- **Axis:** Cross-cutting — new shared `vigil/` module used by all levels
- **New module:** `vigil/inference.py`
- **Depends on:** L0+ (every level makes LLM calls); enables R5 (cost) and R4 (resilience)

---

## Problem / Motivation

Every level instantiates `OpenAI()` directly and hardcodes `gpt-4o-mini`. There is no
**model routing** (cheap model for easy tasks, strong model for hard ones), no
**fallback chain** (if the primary model errors or rate-limits, try another), and no
**streaming**. These are foundational production concerns and a clean seam that R4
(resilience) and R5 (cost) build on.

## Teaching Goal

**A learner introduces a thin inference layer that picks a model per task, falls back
on failure, and streams tokens** — without rewriting any level's logic. They learn
that the model call should be an abstraction, and how routing trades cost against
quality.

## Goals

- A single **`complete()` / `acomplete()`** entry point wrapping OpenAI calls,
  adopted incrementally by levels (start with one, prove it, roll out).
- **Model routing** — choose a model from task metadata (e.g. `task="route"` →
  cheap; `task="critique"` → strong) via a declarative policy, overridable per call.
- **Fallback chain** — ordered list of models; on transient error/rate-limit, try the
  next (composes with R4 retry primitives once R4 exists).
- **Streaming** — `astream()` yielding tokens, surfaced to CLI (`rich.Live`) and API
  (SSE), opt-in so existing callers are unaffected.
- **Centralized pricing** — a `pricing.py` map keyed by model (replaces the per-file
  hardcoded constants), reused by R5.
- Preserves the existing `get_usage()` token-tracking contract.

## Non-Goals

- Multi-provider support (Anthropic/local) — designed to allow it later, not built now.
- Caching (that's R5) or circuit-breaking (that's R4); E4 exposes the seams they use.

## Design

```
caller ──► complete(messages, task="route", schema=…)
                 │
                 ▼
           Router.pick(task, policy)  ─► model = gpt-4o-mini
                 │
                 ▼
        FallbackChain[model, *backups]
                 │  primary error/429
                 ▼
            try next model ──► response ──► _track() (centralized pricing)
```

A declarative policy maps task → preferred model + fallbacks. `OPENAI_MODEL` still
works as a global override so current behavior is the default.

## Proposed Files

- **New** `vigil/inference.py` — `complete`, `acomplete`, `astream`, `Router`,
  `FallbackChain`.
- **New** `vigil/pricing.py` — model → input/output price map; `cost(model, usage)`.
- **Edit** one pilot level (e.g. `levels/l3_routing.py`) to adopt `complete()`;
  document the migration so other levels follow.
- **Edit** `vigil/api.py` — optional `model`/`task` override in requests; SSE stream
  endpoint for one level as a demo.
- **Edit** `pyproject.toml` — no new deps required (OpenAI streaming is built-in).
- **New** `tests/test_inference.py`.

## Data Models (`vigil/models.py`)

```python
class RoutePolicy(_Base):
    task: str
    primary: str
    fallbacks: list[str]

class InferenceResult(_Base):
    model_used: str
    fell_back: bool
    attempts: int
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float
```

## API & CLI Surface

- Analyse endpoints accept optional `{"task": "...", "model": "..."}` overrides.
- `GET /inference/policy` → current routing policy.
- `POST /l1/stream` (demo) — Server-Sent Events token stream.
- CLI: `python levels/l3_routing.py CVE-2021-44228 --model gpt-4o`
- CLI: `python levels/l3_routing.py CVE-2021-44228 --stream`

## Tests (`tests/test_inference.py`)

- Router picks the policy's model for a task; per-call override wins.
- Fallback chain advances to the next model on a stubbed transient error and reports
  `fell_back=True`, `attempts=2`.
- Non-transient error does not trigger fallback.
- `astream()` yields chunks and final usage equals the non-streamed call.
- Centralized `cost()` matches the values previously produced by per-file constants
  (no cost regression).

## Acceptance Criteria

- [ ] At least one level runs through `complete()` with identical output to before.
- [ ] Routing selects models by task; override works.
- [ ] Fallback recovers from a simulated primary-model failure.
- [ ] Streaming works on the demo endpoint and CLI.
- [ ] Pricing centralized; `get_usage()` contract preserved.
- [ ] Conventions followed; tests stub OpenAI, no real calls.

## Open Questions

- Default routing policy contents (which tasks map to `gpt-4o` vs `gpt-4o-mini`)?
  Proposal: only `critique`/`judge`/`plan` go to the stronger model; everything else
  stays cheap.
- Roll out `complete()` to all levels in this spec, or pilot one and migrate the rest
  incrementally? Proposal: pilot L3, migrate others in follow-up PRs to keep diffs
  reviewable.
