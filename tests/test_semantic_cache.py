from __future__ import annotations

from levels.foundations.semantic_cache import SemanticCache, simulate


def test_semantic_cache_hits_on_similar_query():
    cache = SemanticCache(threshold=0.5)
    cache.store("What is CVE-2021-44228?", "Log4Shell RCE")
    result = cache.lookup("Tell me about CVE-2021-44228")
    assert result["hit"] is True
    assert result["response"] == "Log4Shell RCE"


def test_semantic_cache_misses_on_unrelated_query():
    cache = SemanticCache(threshold=0.5)
    cache.store("What is CVE-2021-44228?", "Log4Shell RCE")
    result = cache.lookup("How do I bake bread?")
    assert result["hit"] is False


def test_simulate_reports_hit_for_near_duplicate():
    pairs = [
        {"query": "What is CVE-2021-44228?", "response": "Log4Shell RCE"},
        {"query": "Tell me about CVE-2021-44228", "response": "Log4Shell RCE"},
        {"query": "How do I bake bread?", "response": "flour"},
    ]
    out = simulate(pairs, threshold=0.5)
    assert out["trace"][1]["hit"] is True
    assert out["stats"]["hits"] >= 1
