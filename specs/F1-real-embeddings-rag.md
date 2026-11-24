# F1 — Real Embeddings & Vector RAG (upgrades E1 / L5)

- **Status:** Done
- **Axis:** Foundations (GenAI literacy) — makes Axis-1 semantic memory real
- **Extends / Fixes:** `levels/l5_memory.py`, spec [E1](E1-semantic-memory.md)
- **Depends on:** L5 (episodic memory + PostgreSQL), E1 (semantic_recall scaffold)

---

## Problem / Motivation

E1 shipped the _shape_ of semantic memory, but the embedding function in
`levels/l5_memory.py` (`_embed_text`) is a hand-rolled `blake2b` hash-bucket — it is
**not** a real embedding. Two semantically related CVEs ("deserialization RCE in
Spring" vs "Java object injection") get near-zero similarity because the vectors only
reflect token hashing, not meaning. A learner therefore never sees the single most
important GenAI primitive: turning text into a dense semantic vector and retrieving by
meaning.

## Teaching Goal

**A learner replaces a fake embedding with a real embedding model
(`text-embedding-3-small`), stores vectors in a vector store, and watches the agent
recall a _semantically_ similar prior incident** — even when the wording differs.
They learn embeddings, cosine similarity, ANN search, and how RAG grounds reasoning.

## Goals

- **Real embeddings** via OpenAI `embeddings.create(model="text-embedding-3-small")`
  (1536-dim), wrapped so the call is tracked like every other model call.
- **Pluggable embedding backend** through `VIGIL_EMBED_MODE`:
  - `local` (default) — deterministic offline hash embedding (keeps tests + offline dev working).
  - `openai` — real semantic embeddings.
- **Vector store** — keep the JSONB + Python-cosine path working for any dimension, and
  add an **optional pgvector path** (`analysis_vectors.embedding vector(1536)` + HNSW
  index) that activates when the extension is present.
- **Graceful fallback** — if `openai` mode fails (no key / network), fall back to
  `local` so the agent never crashes.
- Backward compatible: exact-match L5 memory and the existing `semantic_recall` API are
  unchanged in signature.

## Non-Goals

- A separate vector DB service (Chroma/FAISS) — pgvector stays in the existing stack.
- Document-corpus chunking (covered by the optional `data/knowledge/` note below and a
  future doc-RAG lesson); L5 embeds one short summary per analysis, so chunking is N/A.

## Design

```
analysis summary ─► embed_text()                 (VIGIL_EMBED_MODE)
                       ├─ openai → text-embedding-3-small (1536-d)
                       └─ local  → blake2b hash bucket   (32-d, offline)
                              │
                  store vector (JSONB or pgvector)
                              │
new CVE ─► embed_text(query) ─► ANN / cosine top-k (cos ≥ τ) ─► labeled RAG block ─► L5 prompt
```

Dimension note: switching modes changes vector length; cosine returns 0 across mismatched
dims, so re-embed when you change modes (documented; a `--reembed` helper is provided).

### Optional document corpus (stretch)

A `data/knowledge/` folder of short remediation notes can be embedded the same way to
demonstrate RAG over real documents; gated behind the same backend.

## Proposed Files

- **Edit** `levels/l5_memory.py` — add async `embed_text()`, `_embed_text_openai()`,
  rename existing to `_embed_text_local()`; `semantic_recall` + `analyse_cve` await it;
  optional pgvector schema/query path in `init_db`/`semantic_recall`.
- **Edit** `vigil/models.py` — add `embedding_mode` + `embedding_dims` to `RecalledMemory`.
- **Edit** `vigil/api.py` — `GET /l5/similar/{cve_id}` returns the embedding mode used.
- **Edit** `pyproject.toml` — document `VIGIL_EMBED_MODE`; no new Python dep (uses `openai`).
- **Edit/New** `tests/test_semantic_memory.py` — assert local determinism + stubbed openai path.
- **Edit** `README.md` / UI E1 page — show which embedding backend is active.

## Data Models (`vigil/models.py`)

```python
class RecalledMemory(_Base):
    query_cve_id: str
    matches: list[SemanticMatch]
    used_in_prompt: bool
    embedding_mode: str = "local"   # "local" | "openai"
    embedding_dims: int = 32
```

## API & CLI Surface

- `GET /l5/similar/{cve_id}?k=5&threshold=0.55` → `RecalledMemory` (now includes mode/dims).
- CLI: `python levels/l5_memory.py CVE-2022-22965 --recall`
- CLI: `python levels/l5_memory.py --reembed` (re-embed all stored summaries after a mode switch).
- Env: `VIGIL_EMBED_MODE=openai` to enable real embeddings.

## Tests (`tests/test_semantic_memory.py`)

- `local` mode is deterministic and offline (existing test keeps passing).
- `openai` mode is **stubbed** (no network) and returns a fixed 1536-d vector; ranking works.
- Failure in `openai` mode falls back to `local` without raising.
- Threshold filters low-similarity matches; RAG block is labeled data, not instructions.
- Skips gracefully if PostgreSQL/pgvector unavailable.

## Acceptance Criteria

- [x] `VIGIL_EMBED_MODE=openai` produces real `text-embedding-3-small` vectors.
- [x] Default `local` mode keeps all existing tests green and works offline.
- [x] A semantically similar prior (different wording) is recalled above threshold in openai mode.
- [x] pgvector path used when available; JSONB+cosine path otherwise — both return ranked matches.
- [x] Embedding failures fall back, never crash. Conventions + token tracking followed.

## Open Questions

- Pin `text-embedding-3-small` (1536) vs `-large` (3072)? Proposal: `-small` (cost/quality fit).
- pgvector index: HNSW (recall quality, tiny dataset → negligible cost). Confirmed.



