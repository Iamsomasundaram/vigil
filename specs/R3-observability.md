# R3 — Observability & Tracing

- **Status:** Draft
- **Axis:** 3 — Reliability & Safety
- **Module:** `reliability/r3_observability.py`
- **Depends on:** L4 (multi-step tool loop is where traces matter)
- **Checklist:** §7 Observability & Attribution (Prompt/Tool Logging, Traceability, Decision Rationale Logging, Workflow Correlation IDs)

---

## Problem / Motivation

Vigil tracks **tokens** but not **spans**. When the autonomous L6 monitor fires a
wrong alert at 3am, there is no way to reconstruct _why_: which prompts ran, which
tools returned what, which decision branch fired, and how long each took. Production
agents need a correlated trace per request.

## Teaching Goal

**A learner instruments an agent run and views a tree of nested spans** — LLM calls,
tool calls, decisions — each with inputs, outputs, latency, and tokens, all tied to
one correlation id. They learn that observability is structured, queryable, and
hierarchical, not `print()` statements.

## Goals

- A lightweight **tracer** with nested spans via context managers:
  ```python
  with tracer.span("analyse", cve_id=cve) as root:
      with tracer.span("llm.call", model=MODEL): ...
      with tracer.span("tool.fetch_nvd"): ...
  ```
- Each span records: name, attributes, start/end, duration_ms, status, token delta,
  and parent id; the whole run shares one `trace_id` (correlation id).
- **Pluggable exporters**: (a) `rich` tree to console, (b) JSONL to file, (c)
  optional OpenTelemetry OTLP exporter behind an extra.
- A **decorator** `@traced` to wrap existing level functions with minimal edits.
- A `--trace` flag added (in this spec, demonstrated on a wrapped L4 run) that prints
  the full span tree with timings and per-span cost.

## Non-Goals

- Standing up a collector/Jaeger backend (OTLP export is optional and documented only).
- Replacing the existing token-tracking helpers (this complements them).

## Design

```
trace_id = uuid4()
 └─ span "analyse" (cve_id=CVE-…)                      1240ms  $0.0021
     ├─ span "llm.call" (model=gpt-4o-mini)             310ms  812 tok
     ├─ span "tool.fetch_nvd" (status=ok)               420ms
     ├─ span "tool.fetch_epss" (status=ok)              180ms
     ├─ span "decision.route" (track=critical)            5ms
     └─ span "llm.call" (model=gpt-4o-mini)             320ms  640 tok
```

Spans are collected in a `Trace` object; exporters serialize it. The tracer is a
thin in-process implementation (no heavy deps) with an adapter that maps to
OpenTelemetry types when the `otel` extra is installed.

## Proposed Files

- **New** `reliability/r3_observability.py` — `Tracer`, `Span`, `@traced`, exporters.
- **Edit** `vigil/models.py` — `Span`, `Trace` (for JSON/API serialization).
- **Edit** `vigil/api.py` — `GET /r3/trace/{trace_id}`; attach `trace_id` to responses.
- **Edit** `pyproject.toml` — add `otel = ["opentelemetry-sdk", "opentelemetry-exporter-otlp"]` extra.
- **New** `tests/test_observability.py`.

## Data Models (`vigil/models.py`)

```python
class Span(_Base):
    span_id: str
    parent_id: str | None
    name: str
    attributes: dict[str, str]
    start_ms: float
    duration_ms: float
    status: Literal["ok", "error"]
    tokens: int | None

class Trace(_Base):
    trace_id: str
    root_span_id: str
    spans: list[Span]
    total_duration_ms: float
    total_tokens: int
    estimated_cost_usd: float
```

## API & CLI Surface

- Every analyse response gains a `trace_id` field.
- `GET /r3/trace/{trace_id}` → `Trace` (in-memory ring buffer or JSONL lookup).
- CLI: `python reliability/r3_observability.py CVE-2021-44228 --trace`
- CLI: `python reliability/r3_observability.py CVE-2021-44228 --export traces.jsonl`

## Tests (`tests/test_observability.py`)

- Nested spans produce correct parent/child ids and a single `trace_id`.
- Durations are recorded; an exception sets `status="error"` and still closes spans.
- JSONL exporter round-trips to a valid `Trace`.
- `@traced` wraps a function without changing its return value.
- Token deltas attributed to the correct span.

## Acceptance Criteria

- [ ] `--trace` prints a correct nested span tree with timings and cost.
- [ ] One correlation id spans an entire request end-to-end.
- [ ] OTLP export works behind the `otel` extra and is optional.
- [ ] Conventions followed; no real calls in tests.

## Open Questions

- In-memory trace retention size for `GET /r3/trace`? Proposal: ring buffer of last
  N traces, configurable, plus optional JSONL persistence.
- Should L6's background loop auto-export every scan trace? Proposal: yes, JSONL.

## TODO (Deferred)

- Add real span instrumentation inside `levels/l4_tool_use.py` and
  `levels/l6_autonomous.py` internals (per-LLM-turn, per-tool-call, per-decision),
  beyond wrapper-level tracing.
