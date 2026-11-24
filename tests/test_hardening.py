from __future__ import annotations

import importlib

from fastapi.testclient import TestClient


def _patch_l0_module(monkeypatch):
    import levels.l0_single_call as l0

    calls = {"n": 0}

    def fake_explain(cve_id: str) -> str:
        calls["n"] += 1
        return f"analysis for {cve_id}"

    def fake_usage() -> dict:
        return {
            "prompt_tokens": 10,
            "completion_tokens": 20,
            "total_tokens": 30,
            "estimated_cost_usd": 0.0001,
        }

    monkeypatch.setattr(l0, "explain_cve", fake_explain)
    monkeypatch.setattr(l0, "get_usage", fake_usage)
    return calls


def _fresh_api():
    import vigil.api as api

    return importlib.reload(api)


def test_auth_blocks_without_key_and_allows_with_key(monkeypatch):
    calls = _patch_l0_module(monkeypatch)
    api = _fresh_api()
    api._API_KEYS = {"good-key"}
    api._RATE_STATE.clear()

    client = TestClient(api.app)

    r_bad = client.post("/l0/analyse", json={"cve_id": "CVE-1"})
    assert r_bad.status_code == 401

    r_ok = client.post("/l0/analyse", json={"cve_id": "CVE-1"}, headers={"x-api-key": "good-key"})
    assert r_ok.status_code == 200
    assert calls["n"] == 1


def test_rate_limit_enforced(monkeypatch):
    _patch_l0_module(monkeypatch)
    api = _fresh_api()
    api._API_KEYS = set()
    api._RATE_PER_MIN = 1
    api._RATE_STATE.clear()

    client = TestClient(api.app)
    r1 = client.post("/l0/analyse", json={"cve_id": "CVE-1"})
    r2 = client.post("/l0/analyse", json={"cve_id": "CVE-2"})

    assert r1.status_code == 200
    assert r2.status_code == 429


def test_response_cache_hit_on_second_identical_request(monkeypatch):
    calls = _patch_l0_module(monkeypatch)
    api = _fresh_api()
    api._API_KEYS = set()
    api._RATE_PER_MIN = 1000
    api._RATE_STATE.clear()
    api._CACHE._mem.clear()

    client = TestClient(api.app)
    r1 = client.post("/l0/analyse", json={"cve_id": "CVE-SAME"})
    r2 = client.post("/l0/analyse", json={"cve_id": "CVE-SAME"})

    assert r1.status_code == 200 and r2.status_code == 200
    assert r1.json()["cache"]["from_cache"] is False
    assert r2.json()["cache"]["from_cache"] is True
    assert calls["n"] == 1


def test_faithfulness_metric_flags_mismatch():
    from reliability import r2_evaluation as r2

    class _Analysis:
        def model_dump(self):
            return {
                "cvss_score": 9.8,
                "epss_score": 0.9,
                "patch_available": True,
            }

    raw = (
        _Analysis(),
        [
            {"tool": "fetch_nvd_data", "result": {"cvss_score": 7.5}},
            {"tool": "fetch_epss_score", "result": {"score": 0.1}},
        ],
    )

    metric = r2._faithfulness_metric("l4", [raw])
    assert metric.metric_type == "faithfulness"
    assert metric.score < 1.0
