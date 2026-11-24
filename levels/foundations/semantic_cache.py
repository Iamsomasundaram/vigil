"""
VIGIL Foundations F24 — Semantic Caching
"""

from __future__ import annotations

import argparse
import json
import math
import re
import time
from typing import Any

from rich.console import Console

console = Console()

_STOP = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "in", "is", "it",
    "of", "on", "or", "that", "the", "to", "with", "what", "how", "why", "does", "do",
}


def _terms(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]+", text.lower()) if t not in _STOP}


def _cosine(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    return inter / math.sqrt(len(a) * len(b))


class SemanticCache:
    """Similarity-based response cache.

    Unlike an exact-key cache, this returns a stored answer when a new query is
    semantically close enough (cosine over term sets) to a previous one.
    """

    def __init__(self, *, threshold: float = 0.8, ttl_seconds: int = 300) -> None:
        self.threshold = threshold
        self.ttl_seconds = ttl_seconds
        self._entries: list[dict[str, Any]] = []
        self.hits = 0
        self.misses = 0

    def _prune(self, now: float) -> None:
        self._entries = [e for e in self._entries if now - e["created"] <= self.ttl_seconds]

    def lookup(self, query: str) -> dict[str, Any]:
        now = time.time()
        self._prune(now)
        q = _terms(query)
        best = None
        best_sim = 0.0
        for e in self._entries:
            sim = _cosine(q, e["terms"])
            if sim > best_sim:
                best_sim = sim
                best = e
        if best is not None and best_sim >= self.threshold:
            self.hits += 1
            return {
                "hit": True,
                "similarity": round(best_sim, 4),
                "matched_query": best["query"],
                "response": best["response"],
            }
        self.misses += 1
        return {"hit": False, "similarity": round(best_sim, 4), "matched_query": None, "response": None}

    def store(self, query: str, response: str) -> None:
        self._entries.append(
            {"query": query, "terms": _terms(query), "response": response, "created": time.time()}
        )

    def stats(self) -> dict[str, Any]:
        total = self.hits + self.misses
        return {
            "entries": len(self._entries),
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": round(self.hits / total, 4) if total else 0.0,
            "threshold": self.threshold,
            "ttl_seconds": self.ttl_seconds,
        }


def simulate(pairs: list[dict[str, str]], *, threshold: float = 0.8) -> dict[str, Any]:
    """Replay (query, response) pairs; near-duplicate queries should hit cache."""
    cache = SemanticCache(threshold=threshold)
    trace: list[dict[str, Any]] = []
    for p in pairs:
        query = p.get("query", "")
        result = cache.lookup(query)
        if not result["hit"]:
            cache.store(query, p.get("response", ""))
        trace.append({"query": query, "hit": result["hit"], "similarity": result["similarity"]})
    return {"threshold": threshold, "trace": trace, "stats": cache.stats()}


def main() -> None:
    parser = argparse.ArgumentParser(description="F24 semantic cache demo")
    parser.add_argument("--threshold", type=float, default=0.8)
    args = parser.parse_args()

    pairs = [
        {"query": "What is CVE-2021-44228?", "response": "Log4Shell RCE"},
        {"query": "Tell me about CVE-2021-44228", "response": "Log4Shell RCE"},
        {"query": "How do I bake bread?", "response": "Use flour and yeast"},
    ]
    console.print(json.dumps(simulate(pairs, threshold=args.threshold), indent=2))


if __name__ == "__main__":
    main()
