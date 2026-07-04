from __future__ import annotations

from datetime import datetime, timezone

import pytest


class _FakeConn:
    async def execute(self, *_args, **_kwargs):
        return None

    async def fetch(self, query: str, *args):
        if "WHERE cve_id = $1 ORDER BY created_at DESC LIMIT 1" in query:
            return []
        if "FROM analysis_vectors v" in query:
            return [
                {
                    "cve_id": "CVE-A",
                    "summary": "critical remote code execution in internet-facing service",
                    "embedding": [1.0, 0.0, 0.0, 0.0] * 8,
                    "feedback_status": "patched",
                    "created_at": datetime.now(timezone.utc),
                },
                {
                    "cve_id": "CVE-B",
                    "summary": "low severity local issue requiring authentication",
                    "embedding": [0.0, 1.0, 0.0, 0.0] * 8,
                    "feedback_status": "monitoring",
                    "created_at": datetime.now(timezone.utc),
                },
            ]
        return []


@pytest.mark.asyncio
async def test_semantic_recall_returns_ranked_matches():
    from levels.l5_memory import semantic_recall

    conn = _FakeConn()
    out = await semantic_recall(conn, "CVE-QUERY", k=5, threshold=0.1)

    assert len(out) >= 1
    assert out[0].cve_id in {"CVE-A", "CVE-B"}
    assert 0.0 <= out[0].similarity <= 1.0


def test_build_semantic_context_includes_similarity_and_outcome():
    from levels.l5_memory import build_semantic_context
    from vigil.models import SemanticMatch

    text = build_semantic_context(
        [
            SemanticMatch(
                cve_id="CVE-A",
                similarity=0.87,
                summary="prior critical issue",
                outcome="patched",
            )
        ]
    )
    assert "semantic recall" in text.lower()
    assert "CVE-A" in text
    assert "patched" in text


# ─── F1: real embedding backend ───────────────────────────────────────────


class _FakeEmbeddingItem:
    def __init__(self, embedding):
        self.embedding = embedding


class _FakeEmbeddingResponse:
    def __init__(self, embedding):
        self.data = [_FakeEmbeddingItem(embedding)]


@pytest.mark.asyncio
async def test_embed_text_openai_mode_uses_real_embeddings(monkeypatch):
    import levels.l5_memory as l5

    captured = {}

    async def fake_create(model, input):
        captured["model"] = model
        captured["input"] = input
        return _FakeEmbeddingResponse([0.25] * 1536)

    monkeypatch.setattr(l5, "EMBED_MODE", "openai")
    monkeypatch.setattr(l5.client, "embeddings", type("E", (), {"create": staticmethod(fake_create)}))

    vec = await l5.embed_text("critical remote code execution")

    assert len(vec) == 1536
    assert captured["model"] == l5.EMBED_MODEL
    assert "critical" in captured["input"]


@pytest.mark.asyncio
async def test_embed_text_openai_failure_falls_back_to_local(monkeypatch):
    import levels.l5_memory as l5

    async def boom(model, input):
        raise RuntimeError("no network")

    monkeypatch.setattr(l5, "EMBED_MODE", "openai")
    monkeypatch.setattr(l5.client, "embeddings", type("E", (), {"create": staticmethod(boom)}))

    vec = await l5.embed_text("some text")

    # Falls back to the deterministic local embedding instead of raising.
    assert vec == l5._embed_text_local("some text")
    assert len(vec) == l5.EMBED_LOCAL_DIMS


def test_local_mode_is_deterministic_and_offline():
    import levels.l5_memory as l5

    assert l5._embed_text_local("CVE-A rce") == l5._embed_text_local("CVE-A rce")
    assert l5.embedding_dims() in (l5.EMBED_LOCAL_DIMS, l5.EMBED_OPENAI_DIMS)

