# E1 — Semantic Memory / RAG (extends L5)

- **Status:** Draft
- **Axis:** Extension of Axis 1 (Capability) — extends L5 memory
- **Extends:** `levels/l5_memory.py`
- **Depends on:** L5 (episodic/feedback/trend memory + PostgreSQL)

---

## Problem / Motivation

L5 gives Vigil three kinds of memory — episodic (past analyses), feedback (outcomes),
and trend (EPSS/CVSS deltas) — all keyed by exact `cve_id`. What it lacks is
**semantic** memory: the ability to retrieve _related_ prior knowledge that isn't an
exact id match. "We saw a similar deserialization RCE in a Spring component last
quarter — here's what we did" is invisible to L5 today.

## Teaching Goal

**A learner adds vector retrieval over past CVE analyses and watches the agent recall
a semantically similar prior incident** to inform a new one. They learn the
difference between key-value memory and associative/semantic memory, and how RAG
grounds reasoning in an organization's own history.

## Goals

- **Embedding + vector store** for past analyses: embed each analysis summary, store
  vectors in PostgreSQL via **pgvector** (fits the existing DB stack).
- **Semantic retrieval** — given a new CVE, fetch top-k similar prior analyses by
  cosine similarity, with a similarity threshold to avoid spurious matches.
- **RAG injection** — retrieved context is added to the L5 prompt as clearly-labeled
  "relevant prior incidents" (data, not instructions — reuse R1 isolation if present).
- **Memory consolidation** — periodic summarization of old, verbose analyses into
  compact "lessons learned" to fight context bloat (ties to R5 context budgeting).
- Backward compatible: L5's exact-match memory still works; semantic memory is additive.

## Non-Goals

- Replacing PostgreSQL with a dedicated vector DB (pgvector keeps the stack simple).
- A full knowledge graph (noted as a possible future spec).

## Design

```
new CVE ──► embed(summary) ──► pgvector  ANN search (top-k, cos ≥ τ)
                                   │
                                   ▼
                    relevant prior incidents (labeled data block)
                                   │
                                   ▼
            L5 analysis prompt  (episodic + feedback + trend + semantic)
```

Consolidation job: cluster/aged analyses → LLM summarize → store as a higher-level
memory with its own embedding; original rows archived.

## Proposed Files

- **Edit** `levels/l5_memory.py` — add `embed()`, `semantic_recall()`, RAG injection.
- **New** `levels/migrations/` (or inline) — pgvector extension + `embedding` column /
  `analysis_vectors` table.
- **Edit** `vigil/models.py` — `RecalledMemory`, `SemanticMatch`.
- **Edit** `vigil/api.py` — `GET /l5/similar/{cve_id}`.
- **Edit** `pyproject.toml` — note pgvector requirement (DB-side); embeddings via
  existing `openai`.
- **Edit** `tests/conftest.py` / new `tests/test_semantic_memory.py`.

## Data Models (`vigil/models.py`)

```python
class SemanticMatch(_Base):
    cve_id: str
    similarity: float
    summary: str
    outcome: str | None       # from feedback memory, if known

class RecalledMemory(_Base):
    query_cve_id: str
    matches: list[SemanticMatch]
    used_in_prompt: bool
```

## API & CLI Surface

- `GET /l5/similar/{cve_id}?k=5` → `RecalledMemory`.
- CLI: `python levels/l5_memory.py CVE-2022-22965 --recall` (show similar priors).
- Existing L5 CLI now optionally injects semantic context.

## Tests (`tests/test_semantic_memory.py`)

- Embedding call is stubbed; vectors stored and retrieved by similarity ordering.
- Threshold filters out low-similarity matches.
- RAG block is injected as labeled data, not instructions.
- Consolidation summarizes N old analyses into 1 and preserves retrievability.
- Skips gracefully if PostgreSQL/pgvector unavailable (matches existing L5/L6 tests).

## Acceptance Criteria

- [ ] A new CVE recalls a semantically similar prior analysis above threshold.
- [ ] Exact-match L5 memory still functions (backward compatible).
- [ ] Retrieved context is labeled and isolated, not blindly trusted.
- [ ] Consolidation reduces stored verbosity without losing recall.
- [ ] Conventions followed; tests stub embeddings and skip without DB.

## Open Questions

- Embedding model + dimensions (`text-embedding-3-small`, 1536) — confirm and pin.
- pgvector index type (IVFFlat vs HNSW) for the small learning dataset. Proposal:
  HNSW for recall quality; dataset is tiny so cost is negligible.
