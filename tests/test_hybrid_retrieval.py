from __future__ import annotations

from levels.foundations.retrieval_quality import hybrid_lab, hybrid_retrieve, build_index


def test_hybrid_lab_returns_all_modes():
    out = hybrid_lab(query="log4j remote code execution patch", top_k=3)
    assert out["lexical_hits"]
    assert out["vector_hits"]
    assert out["hybrid_hits"]
    assert out["n_chunks"] >= 1


def test_hybrid_retrieve_rerank_changes_scores():
    docs = [
        {"id": "a", "title": "Log4j", "text": "remote code execution log4j patch urgently required"},
        {"id": "b", "title": "Off-topic", "text": "office coffee machine maintenance schedule"},
    ]
    index = build_index(docs, chunk_size_words=20, overlap_words=5)

    base = hybrid_retrieve("log4j remote patch", index, mode="hybrid", rerank=False, top_k=2)
    reranked = hybrid_retrieve("log4j remote patch", index, mode="hybrid", rerank=True, top_k=2)

    assert base[0]["doc_id"] == "a"
    assert reranked[0]["doc_id"] == "a"
    assert reranked[0]["rerank_score"] is not None


def test_hybrid_mode_relevance_beats_offtopic():
    docs = [
        {"id": "a", "title": "Log4j", "text": "remote code execution log4j patch"},
        {"id": "b", "title": "Off-topic", "text": "office snacks and coffee"},
    ]
    index = build_index(docs, chunk_size_words=20, overlap_words=5)
    hits = hybrid_retrieve("log4j patch", index, mode="hybrid", top_k=2)
    assert hits[0]["doc_id"] == "a"
