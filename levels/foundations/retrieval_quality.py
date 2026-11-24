"""
VIGIL Foundations F11 — Data Preparation and Retrieval Index Quality
"""

from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.table import Table

console = Console()

_DEFAULT_DOCS: list[dict[str, str]] = [
    {
        "id": "doc1",
        "title": "Log4j RCE advisory",
        "text": (
            "CVE-2021-44228 allows remote code execution in Apache Log4j 2. "
            "Internet-facing Java services are high risk and should be patched to 2.17.1 or later. "
            "Temporary mitigations include disabling message lookups."
        ),
    },
    {
        "id": "doc2",
        "title": "HTTP/2 Rapid Reset incident note",
        "text": (
            "CVE-2023-44487 is a denial-of-service issue using HTTP/2 request reset behavior. "
            "It can overwhelm edge infrastructure. Priorities include edge rate controls and vendor patching."
        ),
    },
    {
        "id": "doc3",
        "title": "Heartbleed response runbook",
        "text": (
            "CVE-2014-0160 exposes process memory in vulnerable OpenSSL versions. "
            "Actions include key rotation, certificate reissue, and customer password resets."
        ),
    },
]

_STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "in", "is", "it", "of", "on", "or", "that", "the", "to", "with", "this", "these", "those", "was", "were",
}


def _word_tokens(text: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9_\-]+", text.lower())


def _query_terms(query: str) -> list[str]:
    return [t for t in _word_tokens(query) if t not in _STOP_WORDS]


def chunk_text(text: str, *, chunk_size_words: int = 80, overlap_words: int = 20) -> list[str]:
    """Chunk text with fixed word windows and overlap."""
    words = text.split()
    if not words:
        return []

    chunk_size_words = max(20, int(chunk_size_words))
    overlap_words = max(0, int(overlap_words))
    if overlap_words >= chunk_size_words:
        overlap_words = max(0, chunk_size_words - 1)

    step = max(1, chunk_size_words - overlap_words)
    chunks: list[str] = []
    for start in range(0, len(words), step):
        end = min(len(words), start + chunk_size_words)
        piece = " ".join(words[start:end]).strip()
        if piece:
            chunks.append(piece)
        if end >= len(words):
            break
    return chunks


def build_index(
    documents: list[dict[str, str]] | None = None,
    *,
    chunk_size_words: int = 80,
    overlap_words: int = 20,
) -> list[dict[str, Any]]:
    """Create a retrieval index from document chunks."""
    docs = documents or _DEFAULT_DOCS
    index: list[dict[str, Any]] = []

    for d in docs:
        doc_id = d.get("id", "doc")
        title = d.get("title", "untitled")
        text = d.get("text", "")
        parts = chunk_text(text, chunk_size_words=chunk_size_words, overlap_words=overlap_words)
        for i, part in enumerate(parts):
            terms = set(_query_terms(part))
            index.append(
                {
                    "chunk_id": f"{doc_id}:{i}",
                    "doc_id": doc_id,
                    "title": title,
                    "text": part,
                    "terms": terms,
                    "word_count": len(part.split()),
                }
            )
    return index


def _score(query_terms: set[str], chunk_terms: set[str]) -> tuple[float, int, list[str]]:
    if not query_terms:
        return 0.0, 0, []
    overlap = sorted(query_terms.intersection(chunk_terms))
    overlap_count = len(overlap)
    if overlap_count == 0:
        return 0.0, 0, []

    coverage = overlap_count / max(1, len(query_terms))
    density = overlap_count / max(1, len(chunk_terms))
    score = (0.75 * coverage) + (0.25 * density)
    return score, overlap_count, overlap


def retrieve(
    query: str,
    index: list[dict[str, Any]],
    *,
    top_k: int = 5,
    min_score: float = 0.01,
) -> list[dict[str, Any]]:
    """Run lexical retrieval over a chunk index."""
    q_terms = set(_query_terms(query))
    rows: list[dict[str, Any]] = []

    for chunk in index:
        score, overlap_count, overlap_terms = _score(q_terms, chunk.get("terms", set()))
        if score < min_score:
            continue
        rows.append(
            {
                "chunk_id": chunk["chunk_id"],
                "doc_id": chunk["doc_id"],
                "title": chunk["title"],
                "score": round(score, 4),
                "overlap_count": overlap_count,
                "overlap_terms": overlap_terms,
                "word_count": chunk.get("word_count", 0),
                "text_preview": (chunk["text"][:160] + "...") if len(chunk["text"]) > 160 else chunk["text"],
            }
        )

    rows.sort(key=lambda r: (r["score"], r["overlap_count"]), reverse=True)
    return rows[: max(1, int(top_k))]


def _entropy(values: list[int]) -> float:
    total = sum(values)
    if total <= 0:
        return 0.0
    ent = 0.0
    for v in values:
        if v <= 0:
            continue
        p = v / total
        ent -= p * math.log2(p)
    return ent


def retrieval_lab(
    query: str,
    *,
    documents: list[dict[str, str]] | None = None,
    chunk_size_words: int = 80,
    overlap_words: int = 20,
    top_k: int = 5,
) -> dict[str, Any]:
    """One-call report: index build + retrieval + diagnostics."""
    docs = documents or _DEFAULT_DOCS
    index = build_index(docs, chunk_size_words=chunk_size_words, overlap_words=overlap_words)
    hits = retrieve(query, index, top_k=top_k)

    per_doc_counts: dict[str, int] = {}
    for row in hits:
        per_doc_counts[row["doc_id"]] = per_doc_counts.get(row["doc_id"], 0) + 1

    diversity_entropy = round(_entropy(list(per_doc_counts.values())), 4)
    avg_chunk_words = round(sum(c.get("word_count", 0) for c in index) / max(1, len(index)), 2)

    return {
        "query": query,
        "chunk_size_words": int(chunk_size_words),
        "overlap_words": int(overlap_words),
        "top_k": int(top_k),
        "n_docs": len(docs),
        "n_chunks": len(index),
        "avg_chunk_words": avg_chunk_words,
        "diversity_entropy": diversity_entropy,
        "hits": hits,
    }


def load_retrieval_golden(dataset_path: str) -> list[dict[str, Any]]:
    """Load a labeled retrieval benchmark from JSON."""
    p = Path(dataset_path)
    if not p.exists():
        raise FileNotFoundError(f"Dataset not found: {dataset_path}")

    payload = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("Retrieval benchmark must be a JSON list")

    rows: list[dict[str, Any]] = []
    for i, row in enumerate(payload, 1):
        if not isinstance(row, dict):
            raise ValueError(f"Row {i} is not an object")
        query = str(row.get("query", "")).strip()
        rel = row.get("relevant_doc_ids", [])
        if not query:
            raise ValueError(f"Row {i} missing query")
        if not isinstance(rel, list) or not rel:
            raise ValueError(f"Row {i} missing non-empty relevant_doc_ids")
        rows.append(
            {
                "query": query,
                "relevant_doc_ids": [str(x) for x in rel],
            }
        )
    return rows


def recall_at_k(retrieved_doc_ids: list[str], relevant_doc_ids: list[str], k: int) -> float:
    """Recall@k over document ids (not chunk ids)."""
    rel = set(relevant_doc_ids)
    if not rel:
        return 0.0
    top = set(retrieved_doc_ids[: max(1, int(k))])
    return len(rel.intersection(top)) / len(rel)


def reciprocal_rank(retrieved_doc_ids: list[str], relevant_doc_ids: list[str], k: int) -> float:
    """Reciprocal rank of the first relevant item in top-k."""
    rel = set(relevant_doc_ids)
    for i, doc_id in enumerate(retrieved_doc_ids[: max(1, int(k))], 1):
        if doc_id in rel:
            return 1.0 / i
    return 0.0


def _dcg(binary_rels: list[int]) -> float:
    score = 0.0
    for i, rel in enumerate(binary_rels, 1):
        if rel <= 0:
            continue
        score += rel / math.log2(i + 1)
    return score


def ndcg_at_k(retrieved_doc_ids: list[str], relevant_doc_ids: list[str], k: int) -> float:
    """nDCG@k for binary relevance."""
    k_eff = max(1, int(k))
    rel = set(relevant_doc_ids)
    observed = [1 if d in rel else 0 for d in retrieved_doc_ids[:k_eff]]
    ideal = [1] * min(len(rel), k_eff) + [0] * max(0, k_eff - len(rel))
    denom = _dcg(ideal)
    if denom == 0.0:
        return 0.0
    return _dcg(observed) / denom


def evaluate_retrieval_settings(
    *,
    dataset_path: str,
    chunk_size_a: int,
    overlap_a: int,
    chunk_size_b: int,
    overlap_b: int,
    k: int = 5,
    documents: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Compare two chunking configurations on labeled retrieval queries."""
    cases = load_retrieval_golden(dataset_path)
    docs = documents or _DEFAULT_DOCS

    index_a = build_index(docs, chunk_size_words=chunk_size_a, overlap_words=overlap_a)
    index_b = build_index(docs, chunk_size_words=chunk_size_b, overlap_words=overlap_b)

    per_case: list[dict[str, Any]] = []
    sums = {
        "a": {"recall": 0.0, "mrr": 0.0, "ndcg": 0.0},
        "b": {"recall": 0.0, "mrr": 0.0, "ndcg": 0.0},
    }

    for row in cases:
        query = row["query"]
        relevant = row["relevant_doc_ids"]

        hits_a = retrieve(query, index_a, top_k=k)
        hits_b = retrieve(query, index_b, top_k=k)
        docs_a = [h["doc_id"] for h in hits_a]
        docs_b = [h["doc_id"] for h in hits_b]

        a_recall = recall_at_k(docs_a, relevant, k)
        a_mrr = reciprocal_rank(docs_a, relevant, k)
        a_ndcg = ndcg_at_k(docs_a, relevant, k)

        b_recall = recall_at_k(docs_b, relevant, k)
        b_mrr = reciprocal_rank(docs_b, relevant, k)
        b_ndcg = ndcg_at_k(docs_b, relevant, k)

        sums["a"]["recall"] += a_recall
        sums["a"]["mrr"] += a_mrr
        sums["a"]["ndcg"] += a_ndcg
        sums["b"]["recall"] += b_recall
        sums["b"]["mrr"] += b_mrr
        sums["b"]["ndcg"] += b_ndcg

        per_case.append(
            {
                "query": query,
                "relevant_doc_ids": relevant,
                "a": {
                    "retrieved_doc_ids": docs_a,
                    "recall_at_k": round(a_recall, 4),
                    "mrr_at_k": round(a_mrr, 4),
                    "ndcg_at_k": round(a_ndcg, 4),
                },
                "b": {
                    "retrieved_doc_ids": docs_b,
                    "recall_at_k": round(b_recall, 4),
                    "mrr_at_k": round(b_mrr, 4),
                    "ndcg_at_k": round(b_ndcg, 4),
                },
            }
        )

    n = max(1, len(cases))
    avg_a = {
        "recall_at_k": round(sums["a"]["recall"] / n, 4),
        "mrr_at_k": round(sums["a"]["mrr"] / n, 4),
        "ndcg_at_k": round(sums["a"]["ndcg"] / n, 4),
    }
    avg_b = {
        "recall_at_k": round(sums["b"]["recall"] / n, 4),
        "mrr_at_k": round(sums["b"]["mrr"] / n, 4),
        "ndcg_at_k": round(sums["b"]["ndcg"] / n, 4),
    }

    score_a = avg_a["recall_at_k"] + avg_a["mrr_at_k"] + avg_a["ndcg_at_k"]
    score_b = avg_b["recall_at_k"] + avg_b["mrr_at_k"] + avg_b["ndcg_at_k"]
    if score_a > score_b:
        winner = "a"
    elif score_b > score_a:
        winner = "b"
    else:
        winner = "tie"

    return {
        "dataset_path": dataset_path,
        "k": int(k),
        "setting_a": {"chunk_size_words": int(chunk_size_a), "overlap_words": int(overlap_a)},
        "setting_b": {"chunk_size_words": int(chunk_size_b), "overlap_words": int(overlap_b)},
        "summary_a": avg_a,
        "summary_b": avg_b,
        "winner": winner,
        "delta": {
            "recall_at_k": round(avg_b["recall_at_k"] - avg_a["recall_at_k"], 4),
            "mrr_at_k": round(avg_b["mrr_at_k"] - avg_a["mrr_at_k"], 4),
            "ndcg_at_k": round(avg_b["ndcg_at_k"] - avg_a["ndcg_at_k"], 4),
        },
        "cases": per_case,
    }


# ─── F16: Hybrid retrieval + reranking ─────────────────────────────────────


def _hash_embed(terms: set[str], dims: int = 64) -> list[float]:
    """Deterministic offline embedding: hash terms into a fixed vector."""
    vec = [0.0] * dims
    for t in terms:
        h = 0
        for ch in t:
            h = (h * 131 + ord(ch)) & 0xFFFFFFFF
        vec[h % dims] += 1.0
    norm = math.sqrt(sum(v * v for v in vec))
    if norm == 0.0:
        return vec
    return [v / norm for v in vec]


def _cosine(a: list[float], b: list[float]) -> float:
    return max(0.0, min(1.0, sum(x * y for x, y in zip(a, b))))


def _lexical_scores(query_terms: set[str], index: list[dict[str, Any]]) -> dict[str, float]:
    scores: dict[str, float] = {}
    for chunk in index:
        score, _, _ = _score(query_terms, chunk.get("terms", set()))
        scores[chunk["chunk_id"]] = score
    return scores


def _vector_scores(query_terms: set[str], index: list[dict[str, Any]]) -> dict[str, float]:
    q_vec = _hash_embed(query_terms)
    scores: dict[str, float] = {}
    for chunk in index:
        c_vec = chunk.get("_vec")
        if c_vec is None:
            c_vec = _hash_embed(chunk.get("terms", set()))
            chunk["_vec"] = c_vec
        scores[chunk["chunk_id"]] = _cosine(q_vec, c_vec)
    return scores


def _normalize(scores: dict[str, float]) -> dict[str, float]:
    if not scores:
        return {}
    hi = max(scores.values())
    if hi <= 0.0:
        return {k: 0.0 for k in scores}
    return {k: v / hi for k, v in scores.items()}


def _rerank(query_terms: set[str], chunk: dict[str, Any]) -> float:
    """Lightweight cross-encoder proxy: reward exact-term coverage + phrase overlap."""
    chunk_terms = chunk.get("terms", set())
    if not query_terms or not chunk_terms:
        return 0.0
    overlap = query_terms.intersection(chunk_terms)
    coverage = len(overlap) / max(1, len(query_terms))
    early = 0.0
    words = chunk.get("text", "").lower().split()
    head = set(words[:30])
    early = len(query_terms.intersection(head)) / max(1, len(query_terms))
    return round(0.6 * coverage + 0.4 * early, 6)


def hybrid_retrieve(
    query: str,
    index: list[dict[str, Any]],
    *,
    mode: str = "hybrid",
    alpha: float = 0.5,
    rerank: bool = False,
    top_k: int = 5,
) -> list[dict[str, Any]]:
    """Retrieve with lexical, vector, or fused hybrid scoring, optional rerank.

    ``alpha`` weights lexical vs vector in hybrid mode (1.0 = pure lexical).
    """
    q_terms = set(_query_terms(query))
    lex = _normalize(_lexical_scores(q_terms, index))
    vec = _normalize(_vector_scores(q_terms, index))

    fused: dict[str, float] = {}
    for chunk in index:
        cid = chunk["chunk_id"]
        if mode == "lexical":
            fused[cid] = lex.get(cid, 0.0)
        elif mode == "vector":
            fused[cid] = vec.get(cid, 0.0)
        else:
            fused[cid] = alpha * lex.get(cid, 0.0) + (1.0 - alpha) * vec.get(cid, 0.0)

    by_id = {c["chunk_id"]: c for c in index}
    rows: list[dict[str, Any]] = []
    for cid, base in fused.items():
        chunk = by_id[cid]
        rerank_score = _rerank(q_terms, chunk) if rerank else None
        final = rerank_score if rerank else base
        rows.append(
            {
                "chunk_id": cid,
                "doc_id": chunk["doc_id"],
                "title": chunk["title"],
                "mode": mode,
                "lexical_score": round(lex.get(cid, 0.0), 4),
                "vector_score": round(vec.get(cid, 0.0), 4),
                "fused_score": round(base, 4),
                "rerank_score": round(rerank_score, 4) if rerank_score is not None else None,
                "score": round(final, 4),
                "text_preview": (chunk["text"][:160] + "...") if len(chunk["text"]) > 160 else chunk["text"],
            }
        )

    rows.sort(key=lambda r: r["score"], reverse=True)
    return rows[: max(1, int(top_k))]


def hybrid_lab(
    query: str,
    *,
    documents: list[dict[str, str]] | None = None,
    chunk_size_words: int = 80,
    overlap_words: int = 20,
    alpha: float = 0.5,
    rerank: bool = False,
    top_k: int = 5,
) -> dict[str, Any]:
    """Compare lexical, vector, and hybrid retrieval (optionally reranked)."""
    docs = documents or _DEFAULT_DOCS
    index = build_index(docs, chunk_size_words=chunk_size_words, overlap_words=overlap_words)

    modes = {
        "lexical": hybrid_retrieve(query, index, mode="lexical", top_k=top_k),
        "vector": hybrid_retrieve(query, index, mode="vector", top_k=top_k),
        "hybrid": hybrid_retrieve(query, index, mode="hybrid", alpha=alpha, rerank=rerank, top_k=top_k),
    }

    return {
        "query": query,
        "alpha": round(float(alpha), 4),
        "rerank": bool(rerank),
        "top_k": int(top_k),
        "n_chunks": len(index),
        "lexical_hits": modes["lexical"],
        "vector_hits": modes["vector"],
        "hybrid_hits": modes["hybrid"],
    }


def render_hits_table(report: dict[str, Any]) -> None:
    table = Table(title="F11 Retrieval Quality Lab")
    table.add_column("Rank")
    table.add_column("Chunk")
    table.add_column("Score")
    table.add_column("Overlap")
    table.add_column("Preview")

    for i, row in enumerate(report.get("hits", []), 1):
        table.add_row(
            str(i),
            f"{row.get('chunk_id', '?')} ({row.get('title', '?')})",
            f"{float(row.get('score', 0.0)):.4f}",
            ", ".join(row.get("overlap_terms", [])) or "-",
            str(row.get("text_preview", ""))[:90],
        )
    console.print(table)


def main() -> None:
    parser = argparse.ArgumentParser(description="F11 retrieval quality lab")
    parser.add_argument("query", nargs="?", default="log4j remote code execution patch")
    parser.add_argument("--chunk-size", type=int, default=80)
    parser.add_argument("--overlap", type=int, default=20)
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()

    report = retrieval_lab(
        query=args.query,
        chunk_size_words=args.chunk_size,
        overlap_words=args.overlap,
        top_k=args.top_k,
    )
    console.print(
        {
            "query": report["query"],
            "n_docs": report["n_docs"],
            "n_chunks": report["n_chunks"],
            "avg_chunk_words": report["avg_chunk_words"],
            "diversity_entropy": report["diversity_entropy"],
        }
    )
    render_hits_table(report)


if __name__ == "__main__":
    main()
