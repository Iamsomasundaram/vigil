from __future__ import annotations

from levels.foundations.retrieval_quality import (
    evaluate_retrieval_settings,
    ndcg_at_k,
    recall_at_k,
    reciprocal_rank,
)


def test_recall_at_k_basic():
    got = recall_at_k(["doc2", "doc1", "doc3"], ["doc1"], k=2)
    assert got == 1.0


def test_reciprocal_rank_when_first_relevant_is_second():
    got = reciprocal_rank(["doc3", "doc1", "doc2"], ["doc1"], k=3)
    assert got == 0.5


def test_ndcg_at_k_perfect_and_miss():
    perfect = ndcg_at_k(["doc1", "doc2"], ["doc1"], k=2)
    miss = ndcg_at_k(["doc2", "doc3"], ["doc1"], k=2)
    assert perfect == 1.0
    assert miss == 0.0


def test_evaluate_retrieval_settings_returns_expected_shape(tmp_path):
    dataset = tmp_path / "retrieval_golden.json"
    dataset.write_text(
        """
[
  {"query": "log4j patch", "relevant_doc_ids": ["doc1"]},
  {"query": "heartbleed openssl", "relevant_doc_ids": ["doc3"]}
]
        """.strip(),
        encoding="utf-8",
    )

    out = evaluate_retrieval_settings(
        dataset_path=str(dataset),
        chunk_size_a=60,
        overlap_a=10,
        chunk_size_b=120,
        overlap_b=20,
        k=3,
    )

    assert out["dataset_path"] == str(dataset)
    assert out["k"] == 3
    assert out["winner"] in {"a", "b", "tie"}
    assert len(out["cases"]) == 2
    assert 0.0 <= out["summary_a"]["mrr_at_k"] <= 1.0
    assert 0.0 <= out["summary_b"]["ndcg_at_k"] <= 1.0
