# F10 — Production Hardening: Auth, Rate Limiting, Caching, Faithfulness Eval

- **Status:** Draft
- **Axis:** Foundations meets Axis-3 (Reliability) — production gaps
- **Edits:** `vigil/api.py`, `reliability/r5_cost_control.py`, `reliability/r2_evaluation.py`
- **Depends on:** R2 (evals), R5 (cost/caching), L4 (grounding)

---

## Problem / Motivation

The readiness checklist confirms concrete production gaps a learner should experience:
the FastAPI service has **no auth and no rate limiting**, **Redis is in the stack but
unused** (no caching), and evals lack an explicit **faithfulness / groundedness** metric
(does the verdict actually match the NVD/EPSS data it cited?). These are small, high-value
lessons in shipping GenAI safely and cheaply.

## Teaching Goal

**A learner adds API-key auth + rate limiting, a real response/tool cache, and a
faithfulness metric, then sees abuse blocked, repeat calls served from cache, and
ungrounded outputs flagged.** They learn the operational seams every GenAI service needs.

## Goals

- **Auth** — optional API-key dependency (`X-API-Key`) on mutating/LLM endpoints, enabled
  when `VIGIL_API_KEYS` is set; open by default for local learning.
- **Rate limiting** — simple token-bucket per key/IP (in-memory, or Redis when available).
- **Caching** — wire the existing `redis` extra: cache tool results (NVD/EPSS) and
  identical analyse requests with a TTL; cache-hit shown in the response.
- **Faithfulness eval** — add an R2 metric that checks the final verdict's cited numbers
  (CVSS/EPSS/patch) against the tool data; score = fraction grounded.

## Non-Goals

- Full OAuth/JWT/multi-tenant identity (future); distributed rate limiting at scale.

## Design

```
request ─► [api-key check] ─► [rate limit] ─► [cache lookup]
              hit → return cached (+from_cache=true)
              miss → run level → store in cache
R2 adds: faithfulness(verdict, tool_data) → grounded fields / total
```

## Proposed Files

- **Edit** `vigil/api.py` — `api_key` dependency, `RateLimiter`, cache middleware/util.
- **New** `vigil/cache.py` — `get/set` with Redis-or-memory backend + TTL.
- **Edit** `reliability/r5_cost_control.py` — record cache hits in cost attribution.
- **Edit** `reliability/r2_evaluation.py` — `faithfulness` metric + scorecard entry.
- **Edit** `pyproject.toml` — `cache` extra already exists; document env vars.
- **New** `tests/test_hardening.py` — auth blocks/permits; limiter trips; cache hit;
  faithfulness flags an ungrounded verdict.
- **Edit** `ui/app.py` — show `from_cache` and a faithfulness score where relevant.

## Data Models (`vigil/models.py`)

```python
class CacheInfo(_Base):
    from_cache: bool
    key: str
    ttl_seconds: int

class FaithfulnessScore(_Base):
    grounded_fields: int
    total_fields: int
    score: float
    ungrounded: list[str]
```

## API & CLI Surface

- All LLM endpoints accept optional `X-API-Key`; return `cache: CacheInfo` when applicable.
- `GET /admin/ratelimit` (key-gated) → current bucket state.
- Env: `VIGIL_API_KEYS`, `VIGIL_RATE_PER_MIN`, `REDIS_URL`, `VIGIL_CACHE_TTL`.

## Tests (`tests/test_hardening.py`)

- With `VIGIL_API_KEYS` set, missing/invalid key → 401; valid key → 200.
- Exceeding `VIGIL_RATE_PER_MIN` → 429.
- Two identical analyse calls → second is `from_cache=true` (LLM called once).
- Faithfulness flags a verdict whose CVSS doesn't match tool data.

## Acceptance Criteria

- [ ] Auth + rate limiting enforce when configured, open by default locally.
- [ ] Cache serves repeat tool/analyse calls and is visible in responses.
- [ ] R2 scorecard includes a faithfulness metric that catches ungrounded output.
- [ ] Conventions followed; degrades cleanly without Redis.

## Open Questions

- Rate-limit identity: API key first, fall back to client IP? Proposal: yes.
- Cache key: hash of (endpoint, cve_id, model, prompt-version)? Proposal: yes.
