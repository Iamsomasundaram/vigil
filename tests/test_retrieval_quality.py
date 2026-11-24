from __future__ import annotations

from levels.foundations.retrieval_quality import build_index, chunk_text, retrieval_lab, retrieve


def test_chunk_text_overlap_keeps_context_continuity():
    words = [f"w{i}" for i in range(1, 121)]
    text = " ".join(words)

    chunks = chunk_text(text, chunk_size_words=40, overlap_words=10)

    assert len(chunks) >= 3
    first_tail = chunks[0].split()[-10:]
    second_head = chunks[1].split()[:10]
    assert first_tail == second_head


def test_retrieve_prioritizes_relevant_chunk():
    docs = [
        {"id": "a", "title": "Log4j", "text": "remote code execution log4j patch urgently"},
        {"id": "b", "title": "Unrelated", "text": "coffee machine maintenance and office snacks"},
    ]
    index = build_index(docs, chunk_size_words=20, overlap_words=5)

    hits = retrieve("log4j remote patch", index, top_k=2)

    assert hits
    assert hits[0]["doc_id"] == "a"
    assert "log4j" in hits[0]["overlap_terms"]


def test_retrieval_lab_report_shape():
    report = retrieval_lab(
        query="http2 rapid reset ddos",
        chunk_size_words=60,
        overlap_words=15,
        top_k=4,
    )

    assert report["query"]
    assert report["n_docs"] >= 1
    assert report["n_chunks"] >= 1
    assert report["top_k"] == 4
    assert isinstance(report["hits"], list)
