# F11 — Retrieval Data Preparation and Index Quality

- **Status:** Done
- **Axis:** Foundations (GenAI literacy)
- **New module:** `levels/foundations/retrieval_quality.py`
- **Depends on:** F1 (embeddings/RAG), F4 (tokenization)

---

## Problem / Motivation

Most RAG failures are data failures: poor chunking, noisy metadata, weak indexing,
or stale corpora. Learners currently see retrieval usage but not retrieval data
engineering decisions.

## Teaching Goal

**A learner changes chunk size/overlap and sees retrieval hit quality shift in real
time.** They learn that corpus preparation is a first-order GenAI skill.

## Goals

- Build a small retrieval lab with explicit chunking knobs.
- Show retrieval hits with overlap evidence and ranking score.
- Expose diagnostics: chunk count, average chunk size, diversity of top hits.
- Add API and UI entry points so this is runnable without notebooks.

## Non-Goals

- Full production vector DB implementation.
- Cross-encoder reranking (planned in a future spec).

## Design

```
documents -> chunk(size, overlap) -> index terms -> lexical retrieve(query)
         -> ranked hits + diagnostics (coverage, diversity, chunk economics)
```

## Proposed Files

- **New** `levels/foundations/retrieval_quality.py`.
- **Edit** `vigil/models.py` with retrieval lab response models.
- **Edit** `vigil/api.py` add `POST /foundations/retrieval-lab`.
- **Edit** `ui/app.py` add Foundations page for retrieval quality.
- **New** `tests/test_retrieval_quality.py`.
- **Edit** `tests/test_foundations_api.py` with endpoint coverage.

## Data Models (`vigil/models.py`)

```python
class RetrievalHit(_Base):
    chunk_id: str
    doc_id: str
    title: str
    score: float
    overlap_count: int
    overlap_terms: list[str]
    word_count: int
    text_preview: str

class RetrievalLabReport(_Base):
    query: str
    chunk_size_words: int
    overlap_words: int
    top_k: int
    n_docs: int
    n_chunks: int
    avg_chunk_words: float
    diversity_entropy: float
    hits: list[RetrievalHit]
```

## API & CLI Surface

- `POST /foundations/retrieval-lab`.
- CLI: `python -m levels.foundations.retrieval_quality "log4j patch urgency"`.

## Tests

- Chunk overlap behavior is stable and deterministic.
- Relevant chunks rank above irrelevant chunks.
- API endpoint validates and returns expected shape.

## Acceptance Criteria

- [x] Learner can tune chunking and observe changed hit rankings.
- [x] Endpoint returns diagnostics and ranked evidence.
- [x] Tests pass for module and endpoint.

## Open Questions

- Should this lab support hybrid lexical+vector mode now or in F12?





