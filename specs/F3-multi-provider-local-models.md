# F3 — Multi-Provider & Local Models (extends E4)

- **Status:** Implemented
- **Axis:** Foundations (GenAI literacy) — extends Axis-3 inference layer
- **Extends:** `vigil/inference.py` (E4 inference/fallback layer)
- **Depends on:** E4 (policy + fallback chain), R5 (cost control)

---

## Problem / Motivation

Vigil is 100% OpenAI `gpt-4o-mini`. A learner never experiences the real-world
decisions of GenAI engineering: hosted vs **local/open** models, the cost/latency/
privacy trade-offs, provider-agnostic abstraction, and quantization. E4 built a clean
inference seam — F3 uses it to add a **second provider** and a **local model**.

## Teaching Goal

**A learner runs the same level against OpenAI and a local model (Ollama) by changing a
policy, and compares cost, latency, and quality.** They learn the OpenAI-compatible API
surface, why a thin inference seam matters, and when local models are good enough.

## Goals

- **Provider abstraction** — extend E4 policies with a `provider` field
  (`openai` | `ollama` | `openai_compatible`) and a `base_url`.
- **Local model path** — talk to **Ollama** (or any OpenAI-compatible endpoint) using the
  same `AsyncOpenAI` client with a custom `base_url`, no new SDK.
- **Per-task routing** — route cheap/bulk tasks (summaries) to local, high-stakes tasks
  (final verdict) to hosted, via E4 policy.
- **Capability flags** — policy declares `supports_tools` / `supports_json_schema` so the
  layer degrades (e.g., prompt-based JSON) when a local model lacks strict schema.
- **Cost/latency comparison** — emit a small comparison table (ties to R5).

## Non-Goals

- Hosting/serving models or fine-tuning (separate concern).
- vLLM/TGI deployment — Ollama is the teaching target; others work via `base_url`.

## Design

```
task ─► E4 policy ─► provider?
            ├─ openai            → api.openai.com
            ├─ ollama            → http://localhost:11434/v1  (OpenAI-compatible)
            └─ openai_compatible → custom base_url
        capability flags → strict JSON vs prompt-coerced JSON; tools vs no-tools
```

## Proposed Files

- **Edit** `vigil/inference.py` — `provider`, `base_url`, `supports_*` in policy; client
  factory keyed by provider; prompt-based JSON fallback.
- **Edit** `vigil/pricing.py` — local model = $0 token cost; record latency.
- **Edit** `vigil/api.py` — `GET /inference/providers`, `POST /inference/compare`.
- **Edit** `pyproject.toml` — no new dep (Ollama via OpenAI-compatible API). Doc env vars.
- **New** `tests/test_providers.py` — stub both clients; assert routing + JSON fallback.
- **Edit** `ui/app.py` — E4 page gains a provider selector + comparison table.

## Data Models (`vigil/models.py`)

```python
class ProviderInfo(_Base):
    name: str
    base_url: str
    supports_tools: bool
    supports_json_schema: bool

class InferenceComparison(_Base):
    task: str
    rows: list[dict]   # provider, latency_ms, tokens, est_cost_usd, output_preview
```

## API & CLI Surface

- `GET /inference/providers` → `list[ProviderInfo]`.
- `POST /inference/compare` `{task, cve_id}` → `InferenceComparison`.
- Env: `OLLAMA_BASE_URL` (default `http://localhost:11434/v1`), `VIGIL_LOCAL_MODEL`.

## Tests (`tests/test_providers.py`)

- Policy with `provider=ollama` builds a client with the right `base_url`.
- A model lacking `supports_json_schema` uses prompt-coerced JSON and still validates.
- Comparison aggregates latency/tokens/cost per provider (clients stubbed).

## Acceptance Criteria

- [ ] Same level runs against OpenAI and Ollama by switching policy only.
- [ ] JSON output works on a non-schema model via fallback coercion.
- [ ] Comparison table shows latency/cost/quality side by side.
- [ ] Degrades clearly if Ollama isn't running; conventions followed.

## Open Questions

- Default local model (`llama3.1:8b` vs `qwen2.5:7b`)? Proposal: `llama3.1:8b`.
- Where to enforce capability degradation — in `acomplete_json` only, or globally?
