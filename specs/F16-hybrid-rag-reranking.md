# F16 — Hybrid Retrieval and Reranking

- **Status:** Done
- **Axis:** Foundations (GenAI literacy)
- **Target:** retrieval stack and evaluation bridge
- **Depends on:** F11, F12, F13

---

## Problem / Motivation

Industry RAG systems rarely rely on one retriever. Production quality generally
uses hybrid lexical+vector retrieval and often a reranker to improve top-k
relevance and citation quality.

## Teaching Goal

**A learner can compare lexical-only, vector-only, and hybrid retrieval with and
without reranking, then justify the best configuration from metrics.**

## Goals

- Add hybrid retrieval mode (BM25-style lexical + embedding similarity fusion).
- Add optional reranking stage for final top-k.
- Show impact on Recall@k, MRR, nDCG, and faithfulness support.
- Keep a deterministic offline demo mode for tests.

## Non-Goals

- Large-scale distributed search infra.

## Proposed Files

- **Edit** `levels/foundations/retrieval_quality.py`
- **Edit** `vigil/api.py` add hybrid/rerank endpoint options
- **Edit** `ui/app.py` add hybrid-rag comparison controls
- **New** `tests/test_hybrid_retrieval.py`

## Acceptance Criteria

- [x] Hybrid mode outperforms single-mode retrieval on provided benchmark.
- [x] Reranking can be toggled and its effects are visible in metrics.
- [x] Deterministic tests cover fusion and ranking behavior.

