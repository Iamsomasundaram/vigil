# R4 — Resilience in the Agent Loop

- **Status:** Draft
- **Axis:** 3 — Reliability & Safety
- **Module:** `reliability/r4_resilience.py`
- **Depends on:** L4 (external tool calls) and L6 (long-running loop)
- **Checklist:** §2 Agent Architecture (Fallback Strategy, Stop Conditions, Loop Limits)

---

## Problem / Motivation

Today, if NVD or EPSS is down mid-loop, behavior is undefined — the analysis either
crashes or silently produces a low-confidence verdict. The long-running L6 monitor is
especially fragile: one transient failure can kill the loop or, worse, generate a
bogus alert. Production agents need retries, timeouts, circuit breakers, and graceful
degradation.

## Teaching Goal

**A learner injects flaky/slow/failing tools and watches the agent recover** —
retrying with backoff, timing out cleanly, tripping a circuit breaker after repeated
failures, and degrading to a partial-but-honest verdict instead of crashing or
hallucinating. They learn that reliability is designed into the loop, not bolted on.

## Goals

- Reusable resilience primitives wrapping any tool/LLM call:
  - **Timeout** — per-call deadline (`httpx` timeout + `asyncio.wait_for`).
  - **Retry with backoff + jitter** — bounded attempts on transient errors only.
  - **Circuit breaker** — open after N consecutive failures, half-open probe, close
    on success; short-circuits calls while open.
  - **Graceful degradation** — if a data source is unavailable, the verdict is
    produced from remaining sources and explicitly marks reduced confidence and
    which sources were missing.
- **Idempotency** for the L6 scan step so a retried scan does not double-write
  alerts/state.
- A **fault-injection harness** (`--chaos`) that wraps the real tools to fail/delay
  on demand for the demo and tests.

## Non-Goals

- Distributed/queue-based retry infrastructure (in-process is sufficient).
- Rate limiting (touched by R5 cost control instead).

## Design

```
call(tool, args)
   └─ CircuitBreaker.guard
        └─ retry(max=3, backoff=exp+jitter, on=TransientError)
             └─ timeout(deadline)
                  └─ tool(args)
   on exhaustion ─► degrade(): mark source missing, lower confidence
```

Primitives are composable decorators/wrappers so L4's tool functions and L6's scan
step opt in with a single wrap. Degradation surfaces through a `confidence` field
and a `degraded_sources` list on the verdict.

## Proposed Files

- **New** `reliability/r4_resilience.py` — `with_timeout`, `with_retry`,
  `CircuitBreaker`, `degrade`, `--chaos` harness.
- **Edit** `vigil/models.py` — add resilience fields to a verdict wrapper.
- **Edit** `vigil/api.py` — `GET /r4/health` (circuit states), `POST /r4/analyse`.
- **New** `tests/test_resilience.py`.

## Data Models (`vigil/models.py`)

```python
class SourceStatus(_Base):
    name: str                 # "nvd", "epss", "kev"
    available: bool
    attempts: int
    circuit: Literal["closed", "open", "half_open"]

class ResilientVerdict(_Base):
    cve_id: str
    confidence: float                 # lowered when sources degrade
    degraded_sources: list[str]
    sources: list[SourceStatus]
    summary: str
```

## API & CLI Surface

- `POST /r4/analyse` — `{cve_id}` → `ResilientVerdict` + `TokenUsage`.
- `GET /r4/health` — current circuit-breaker states per source.
- CLI: `python reliability/r4_resilience.py CVE-2021-44228`
- CLI: `python reliability/r4_resilience.py CVE-2021-44228 --chaos epss=timeout,nvd=500`

## Tests (`tests/test_resilience.py`)

- Retry succeeds after N transient failures, then stops at the cap.
- Non-transient errors (e.g. 400) are not retried.
- Timeout aborts a slow call within the deadline.
- Circuit breaker opens after the threshold and short-circuits subsequent calls.
- A failed source yields a degraded verdict with lowered confidence, not a crash.
- L6 scan step is idempotent under a retried invocation (no duplicate alerts).

## Acceptance Criteria

- [ ] `--chaos` reliably reproduces timeout/500/flaky behavior for the demo.
- [ ] All four primitives are independently unit-tested.
- [ ] Degraded runs never fabricate missing data; they flag it.
- [ ] L6 scan idempotency verified.
- [ ] Conventions followed; tests use stubs, no real calls.

## Open Questions

- Circuit-breaker state: per-process only, or persisted in Redis for L6 restarts?
  Proposal: in-process default, optional Redis backing behind the `api` extra.
- Confidence formula when multiple sources degrade — linear penalty vs. weighted?
