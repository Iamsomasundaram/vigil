from __future__ import annotations

import importlib

from fastapi.testclient import TestClient


def _fresh_api():
    import vigil.api as api

    return importlib.reload(api)


def test_foundations_tokenize_endpoint(monkeypatch):
    import levels.foundations.tokenization as tok

    monkeypatch.setattr(
        tok,
        "tokenize_report",
        lambda text, model="gpt-4o-mini": {
            "model": model,
            "text_preview": text,
            "token_count": 5,
            "context_limit": 128000,
            "pct_of_context": 0.0039,
            "est_cost_usd": 0.0,
            "sample_tokens": ["CVE", "-", "2021"],
        },
    )

    api = _fresh_api()
    client = TestClient(api.app)

    r = client.post("/foundations/tokenize", json={"text": "CVE-2021-44228"})
    assert r.status_code == 200
    body = r.json()
    assert body["token_count"] == 5
    assert body["sample_tokens"][0] == "CVE"


def test_l4_tools_discovery_endpoint(monkeypatch):
    import levels.l4_tool_use as l4

    monkeypatch.setattr(
        l4,
        "discover_tools",
        lambda source="inline": [
            {
                "name": "fetch_nvd_data",
                "description": "d",
                "input_schema": {"type": "object"},
                "source": source,
            }
        ],
    )

    api = _fresh_api()
    client = TestClient(api.app)

    r = client.get("/l4/tools", params={"source": "mcp"})
    assert r.status_code == 200
    row = r.json()[0]
    assert row["name"] == "fetch_nvd_data"
    assert row["source"] == "mcp"


def test_framework_a1_endpoint(monkeypatch):
    import architectures.frameworks.a1_react_langgraph as f7

    async def fake_analyse(cve_id: str):
        return {"cve_id": cve_id, "framework": "langgraph", "verdict": "ok"}

    monkeypatch.setattr(f7, "analyse_cve", fake_analyse)

    api = _fresh_api()
    client = TestClient(api.app)

    r = client.post("/frameworks/a1", json={"cve_id": "CVE-2021-0001"})
    assert r.status_code == 200
    assert r.json()["framework"] == "langgraph"


def test_foundations_retrieval_lab_endpoint(monkeypatch):
    import levels.foundations.retrieval_quality as rq

    monkeypatch.setattr(
        rq,
        "retrieval_lab",
        lambda query, chunk_size_words=80, overlap_words=20, top_k=5: {
            "query": query,
            "chunk_size_words": chunk_size_words,
            "overlap_words": overlap_words,
            "top_k": top_k,
            "n_docs": 2,
            "n_chunks": 4,
            "avg_chunk_words": 72.5,
            "diversity_entropy": 0.811,
            "hits": [
                {
                    "chunk_id": "doc1:0",
                    "doc_id": "doc1",
                    "title": "Doc 1",
                    "score": 0.89,
                    "overlap_count": 3,
                    "overlap_terms": ["log4j", "patch"],
                    "word_count": 68,
                    "text_preview": "CVE summary...",
                }
            ],
        },
    )

    api = _fresh_api()
    client = TestClient(api.app)

    r = client.post(
        "/foundations/retrieval-lab",
        json={"query": "log4j patch", "chunk_size_words": 60, "overlap_words": 10, "top_k": 3},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["query"] == "log4j patch"
    assert body["hits"][0]["chunk_id"] == "doc1:0"


def test_theme_incident_endpoint(monkeypatch):
    import levels.themes.incident_ops as t1
    from vigil.models import IncidentOpsReport

    monkeypatch.setattr(
        t1,
        "analyse_incident",
        lambda alert_text, service_name, customer_impact, signals: IncidentOpsReport(
            service_name=service_name,
            severity="High",
            track="mitigation",
            summary="Service degraded.",
            urgency_minutes=60,
            likely_domains=["identity"],
            immediate_actions=["Scale up"],
            escalation_targets=["on-call-sre"],
            reasoning="signal match",
        ),
    )

    api = _fresh_api()
    client = TestClient(api.app)

    r = client.post(
        "/themes/incident/analyse",
        json={
            "alert_text": "timeouts and auth failures",
            "service_name": "auth-api",
            "customer_impact": True,
            "signals": ["latency"],
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["theme"] == "T1"
    assert body["report"]["track"] == "mitigation"


def test_foundations_retrieval_eval_endpoint(monkeypatch):
    import levels.foundations.retrieval_quality as rq

    monkeypatch.setattr(
        rq,
        "evaluate_retrieval_settings",
        lambda **_: {
            "dataset_path": "data/eval/retrieval_golden.json",
            "k": 5,
            "setting_a": {"chunk_size_words": 80, "overlap_words": 20},
            "setting_b": {"chunk_size_words": 120, "overlap_words": 20},
            "summary_a": {"recall_at_k": 0.66, "mrr_at_k": 0.55, "ndcg_at_k": 0.61},
            "summary_b": {"recall_at_k": 0.66, "mrr_at_k": 0.67, "ndcg_at_k": 0.70},
            "winner": "b",
            "delta": {"recall_at_k": 0.0, "mrr_at_k": 0.12, "ndcg_at_k": 0.09},
            "cases": [
                {
                    "query": "log4j remote code execution patch",
                    "relevant_doc_ids": ["doc1"],
                    "a": {"retrieved_doc_ids": ["doc1"], "recall_at_k": 1.0, "mrr_at_k": 1.0, "ndcg_at_k": 1.0},
                    "b": {"retrieved_doc_ids": ["doc1"], "recall_at_k": 1.0, "mrr_at_k": 1.0, "ndcg_at_k": 1.0},
                }
            ],
        },
    )

    api = _fresh_api()
    client = TestClient(api.app)
    r = client.post("/foundations/retrieval-eval", json={"k": 5})
    assert r.status_code == 200
    body = r.json()
    assert body["winner"] == "b"
    assert body["summary_b"]["mrr_at_k"] > body["summary_a"]["mrr_at_k"]


def test_foundations_factuality_check_endpoint(monkeypatch):
    import levels.foundations.factuality as f13

    monkeypatch.setattr(
        f13,
        "factuality_check",
        lambda **_: {
            "faithfulness_score": 0.66,
            "supported_claims": 2,
            "total_claims": 3,
            "unsupported_claims": ["Unsupported statement"],
            "abstain_recommended": True,
            "results": [
                {
                    "claim": "Statement A",
                    "supported": True,
                    "support_score": 0.9,
                    "evidence_excerpt": "Proof A",
                }
            ],
        },
    )

    api = _fresh_api()
    client = TestClient(api.app)
    r = client.post(
        "/foundations/factuality-check",
        json={
            "answer_text": "Statement A. Unsupported statement.",
            "evidence_snippets": ["Proof A"],
            "support_threshold": 0.45,
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["abstain_recommended"] is True
    assert body["supported_claims"] == 2


def test_foundations_prompt_versions_endpoints(monkeypatch):
    import levels.foundations.prompt_lifecycle as f14

    monkeypatch.setattr(
        f14,
        "list_versions",
        lambda path="": [
            {"id": "v1", "name": "n1", "template": "t1", "notes": "a"},
            {"id": "v2", "name": "n2", "template": "t2", "notes": "b"},
        ],
    )
    monkeypatch.setattr(
        f14,
        "compare_versions",
        lambda **_: {
            "version_a": "v1",
            "version_b": "v2",
            "overall_winner": "b",
            "summary": {
                "a_avg_quality": 0.61,
                "b_avg_quality": 0.73,
                "a_wins": 1,
                "b_wins": 2,
                "ties": 0,
            },
            "per_item": [
                {"item": "CVE-2021-0001", "a_quality": 0.6, "b_quality": 0.7, "winner": "b"},
            ],
        },
    )

    api = _fresh_api()
    client = TestClient(api.app)

    rv = client.get("/foundations/prompt-versions")
    assert rv.status_code == 200
    assert rv.json()[0]["id"] == "v1"

    rc = client.post("/foundations/prompt-versions/compare", json={"version_a": "v1", "version_b": "v2", "items": ["CVE-2021-0001"]})
    assert rc.status_code == 200
    assert rc.json()["overall_winner"] == "b"


def test_foundations_privacy_redact_endpoint(monkeypatch):
    import levels.foundations.privacy as f15

    monkeypatch.setattr(
        f15,
        "privacy_report",
        lambda text, sample_payload=None: {
            "input_length": len(text),
            "changed": True,
            "findings": [{"type": "email", "count": 1}],
            "redacted_text": "<REDACTED_EMAIL>",
            "safe_log_snapshot": {"msg": "<REDACTED_EMAIL>"},
        },
    )

    api = _fresh_api()
    client = TestClient(api.app)
    r = client.post("/foundations/privacy/redact", json={"text": "user@example.com"})
    assert r.status_code == 200
    body = r.json()
    assert body["changed"] is True
    assert body["findings"][0]["type"] == "email"


def test_foundations_hybrid_retrieval_endpoint():
    api = _fresh_api()
    client = TestClient(api.app)
    r = client.post(
        "/foundations/hybrid-retrieval",
        json={"query": "log4j remote code execution patch", "rerank": True, "top_k": 3},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["hybrid_hits"]
    assert body["rerank"] is True


def test_reliability_drift_endpoints():
    api = _fresh_api()
    client = TestClient(api.app)
    for _ in range(12):
        s = client.post(
            "/reliability/drift/sample",
            json={"quality": 0.4, "latency_ms": 1000, "cost_usd": 0.003},
        )
        assert s.status_code == 200
    r = client.post("/reliability/drift/report", json={"baseline_quality": 0.8})
    assert r.status_code == 200
    assert "quality_below_slo" in r.json()["breaches"]


def test_reliability_action_check_endpoint():
    api = _fresh_api()
    client = TestClient(api.app)
    r = client.post(
        "/reliability/action/check",
        json={"role": "viewer", "tool": "apply_patch", "requested_sandbox": "execute"},
    )
    assert r.status_code == 200
    assert r.json()["allowed"] is False


def test_reliability_supply_chain_endpoints():
    api = _fresh_api()
    client = TestClient(api.app)
    v = client.get("/reliability/supply-chain/verify")
    assert v.status_code == 200
    assert v.json()["integrity_ok"] is True

    p = client.post("/reliability/supply-chain/promote", json={"eval_passed": False})
    assert p.status_code == 200
    assert p.json()["allowed"] is False


def test_reliability_release_evaluate_endpoint():
    api = _fresh_api()
    client = TestClient(api.app)
    r = client.post(
        "/reliability/release/evaluate",
        json={"control_scores": [0.8, 0.82], "treatment_scores": [0.7, 0.69]},
    )
    assert r.status_code == 200
    assert r.json()["decision"] == "rollback"


def test_foundations_adaptation_recommend_endpoint():
    api = _fresh_api()
    client = TestClient(api.app)
    r = client.post(
        "/foundations/adaptation/recommend",
        json={"needs_fresh_knowledge": True, "data_volume": 50},
    )
    assert r.status_code == 200
    assert r.json()["recommended"] == "rag"


def test_foundations_finetune_validate_endpoint():
    api = _fresh_api()
    client = TestClient(api.app)
    records = [
        {"messages": [{"role": "user", "content": f"q{i}"}, {"role": "assistant", "content": f"a{i}"}]}
        for i in range(12)
    ]
    r = client.post("/foundations/finetune/validate", json={"records": records})
    assert r.status_code == 200
    assert r.json()["ready_to_train"] is True


def test_foundations_model_select_endpoint():
    api = _fresh_api()
    client = TestClient(api.app)
    r = client.post(
        "/foundations/model-select",
        json={"task_complexity": "high", "high_stakes": True},
    )
    assert r.status_code == 200
    assert r.json()["recommended"] == "opus"


def test_claude_map_messages_endpoint():
    api = _fresh_api()
    client = TestClient(api.app)
    r = client.post(
        "/claude/map-messages",
        json={
            "messages": [
                {"role": "system", "content": "You are an analyst."},
                {"role": "user", "content": "Hi"},
            ]
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["system"] == "You are an analyst."
    assert body["messages"][0]["role"] == "user"


def test_mcp_tool_loop_endpoint(monkeypatch):
    import vigil_mcp.vigil_client as client_mod

    async def fake_invoke(name, args):
        return {"tool": name, "cve_id": args.get("cve_id"), "ok": True}

    monkeypatch.setattr(client_mod, "invoke", fake_invoke)

    api = _fresh_api()
    client = TestClient(api.app)
    r = client.post("/mcp/tool-loop", json={"cve_id": "CVE-2021-44228"})
    assert r.status_code == 200
    assert r.json()["tool_calls"] == 2


def test_foundations_responsible_ai_endpoint():
    api = _fresh_api()
    client = TestClient(api.app)
    r = client.post(
        "/foundations/responsible-ai",
        json={
            "texts": ["You stupid loser"],
            "outcomes": [{"group": "a", "positive": True}, {"group": "b", "positive": False}],
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["flagged_texts"] == 1
    assert body["safe_to_ship"] is False


def test_foundations_semantic_cache_endpoint():
    api = _fresh_api()
    client = TestClient(api.app)
    r = client.post(
        "/foundations/semantic-cache",
        json={
            "pairs": [
                {"query": "What is CVE-2021-44228?", "response": "Log4Shell"},
                {"query": "Tell me about CVE-2021-44228", "response": "Log4Shell"},
            ],
            "threshold": 0.5,
        },
    )
    assert r.status_code == 200
    assert r.json()["stats"]["hits"] >= 1




