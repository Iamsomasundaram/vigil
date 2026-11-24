# F24 — Semantic Caching

- **Status:** Done
- **Axis:** Foundations (cost & latency optimization)
- **Target:** `levels/foundations/semantic_cache.py`
- **Depends on:** F1, F10, R5

---

## Problem / Motivation

Exact-key response caches miss on paraphrased queries. Semantic caching reuses a
stored answer when a new query is similar enough, cutting cost and latency where
exact caches fail.

## Teaching Goal

**A learner can explain semantic vs exact-key caching and tune a similarity
threshold to balance reuse against false hits.**

## Goals

- Similarity-based cache with cosine over term sets, TTL, and hit/miss stats.
- Replay simulator showing per-query hit/miss and hit rate.
- API + UI to tune the threshold interactively.
- Deterministic and offline for tests.

## Non-Goals

- Real embedding-backed vector cache or distributed cache infra.

## Files Delivered

- **New** `levels/foundations/semantic_cache.py`
- **Edit** `vigil/models.py`, `vigil/api.py`, `ui/app.py`
- **New** `tests/test_semantic_cache.py`

## API & CLI Surface

- `POST /foundations/semantic-cache`
- CLI: `python -m levels.foundations.semantic_cache --threshold 0.8`

## Acceptance Criteria

- [x] Similar queries hit; unrelated queries miss.
- [x] Threshold controls hit rate; stats report hits/misses/hit-rate.
- [x] Simulator and endpoint are deterministic and test-covered.
