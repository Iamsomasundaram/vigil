from __future__ import annotations

import importlib
import os

import pytest
from fastapi.testclient import TestClient

from vigil import hardening


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


def _fresh_api(monkeypatch=None, **env):
    """Reload hardening (re-reads env, resets module state) and the app that registers it."""
    import vigil.api as api

    if monkeypatch is not None:
        for name in ("VIGIL_ENV", "VIGIL_API_KEYS", "VIGIL_CORS_ORIGINS"):
            monkeypatch.delenv(name, raising=False)
        for name, value in env.items():
            monkeypatch.setenv(name, value)
    importlib.reload(hardening)
    return importlib.reload(api)


@pytest.fixture(autouse=True)
def _restore_hardening_defaults():
    """Other test files share the module; leave it in its default (dev, no keys) state."""
    yield
    for name in ("VIGIL_ENV", "VIGIL_API_KEYS", "VIGIL_CORS_ORIGINS"):
        os.environ.pop(name, None)
    importlib.reload(hardening)


CVE = "CVE-2021-44228"
KEYS = "reader:rk:read,runner:uk:run,ops:ak:admin"


def _client(monkeypatch, **env):
    return TestClient(_fresh_api(monkeypatch, **env).app)


# ─── auth: deny by default ───────────────────────────────────────────────────

def test_auth_blocks_without_key_and_allows_with_key(monkeypatch):
    calls = _patch_l0_module(monkeypatch)
    client = _client(monkeypatch, VIGIL_API_KEYS="good-key")

    assert client.post("/l0/analyse", json={"cve_id": CVE}).status_code == 401
    ok = client.post("/l0/analyse", json={"cve_id": CVE}, headers={"x-api-key": "good-key"})
    assert ok.status_code == 200
    assert calls["n"] == 1


def test_every_route_needs_a_key_once_keys_are_set_except_health(monkeypatch):
    client = _client(monkeypatch, VIGIL_API_KEYS=KEYS)

    assert client.get("/health").status_code == 200
    # routes the old prefix list left open: GETs, A1-A4, kill switch, budget, MCP loop
    for method, path in [
        ("GET", f"/l5/history/{CVE}"),
        ("GET", "/l6/watchlist"),
        ("GET", "/l1/stream"),
        ("POST", "/a1/analyse"),
        ("POST", "/l6/monitor/stop"),
        ("POST", "/r5/budget"),
        ("POST", "/mcp/tool-loop"),
        ("GET", "/admin/ratelimit"),
    ]:
        assert client.request(method, path).status_code == 401, (method, path)


def test_bad_key_is_rejected(monkeypatch):
    client = _client(monkeypatch, VIGIL_API_KEYS=KEYS)
    r = client.get("/l6/watchlist", headers={"x-api-key": "wrong"})
    assert r.status_code == 401


# ─── scopes ──────────────────────────────────────────────────────────────────

def test_read_key_can_read_but_not_run(monkeypatch):
    _patch_l0_module(monkeypatch)
    client = _client(monkeypatch, VIGIL_API_KEYS=KEYS)
    h = {"x-api-key": "rk"}

    assert client.get("/foundations/prompt-versions", headers=h).status_code == 200
    r = client.post("/l0/analyse", json={"cve_id": CVE}, headers=h)
    assert r.status_code == 403
    assert "needs 'run'" in r.json()["detail"]


def test_run_key_cannot_use_admin_routes(monkeypatch):
    _patch_l0_module(monkeypatch)
    client = _client(monkeypatch, VIGIL_API_KEYS=KEYS)
    h = {"x-api-key": "uk"}

    assert client.post("/l0/analyse", json={"cve_id": CVE}, headers=h).status_code == 200
    assert client.post("/l6/monitor/stop", headers=h).status_code == 403
    assert client.post("/r5/budget", json={}, headers=h).status_code == 403
    assert client.get("/admin/ratelimit", headers=h).status_code == 403


def test_admin_key_can_use_admin_routes_and_buckets_use_names_not_keys(monkeypatch):
    _patch_l0_module(monkeypatch)
    client = _client(monkeypatch, VIGIL_API_KEYS=KEYS)
    h = {"x-api-key": "ak"}

    client.post("/l0/analyse", json={"cve_id": CVE}, headers=h)
    r = client.get("/admin/ratelimit", headers=h)
    assert r.status_code == 200
    assert "ops" in r.json()["buckets"]
    assert "ak" not in r.json()["buckets"]  # the secret is never used as an identifier


def test_parse_api_keys_formats_and_errors():
    assert hardening.parse_api_keys("") == {}
    assert hardening.parse_api_keys("solo") == {"solo": ("key0", "admin")}
    assert hardening.parse_api_keys("a:k1:read, b:k2:run") == {"k1": ("a", "read"), "k2": ("b", "run")}
    for bad in ("a:k:superuser", "a:k", "a:k:read,b:k:run", ":k:read"):
        with pytest.raises(ValueError):
            hardening.parse_api_keys(bad)


# ─── dev vs prod ─────────────────────────────────────────────────────────────

def test_dev_without_keys_is_open_and_warns(monkeypatch, caplog):
    _patch_l0_module(monkeypatch)
    client = _client(monkeypatch)

    assert client.post("/l0/analyse", json={"cve_id": CVE}).status_code == 200
    assert client.get("/docs").status_code == 200
    with caplog.at_level("WARNING", logger="vigil.hardening"):
        hardening.validate_config()
    assert "API is OPEN" in caplog.text


def test_prod_without_keys_refuses_to_start_and_denies_requests(monkeypatch):
    client = _client(monkeypatch, VIGIL_ENV="prod")

    with pytest.raises(RuntimeError, match="requires VIGIL_API_KEYS"):
        hardening.validate_config()
    with pytest.raises(RuntimeError):
        with TestClient(client.app):  # runs the lifespan, as uvicorn does
            pass
    # even if it were running, it fails closed
    assert client.get("/health").status_code == 200
    assert client.get("/l6/watchlist").status_code == 401


def test_prod_with_keys_starts_and_protects_docs(monkeypatch):
    client = _client(monkeypatch, VIGIL_ENV="prod", VIGIL_API_KEYS=KEYS)

    hardening.validate_config()  # no error
    assert client.get("/docs").status_code == 401
    assert client.get("/docs", headers={"x-api-key": "rk"}).status_code == 200


# ─── rate limit, brute force, concurrency ────────────────────────────────────

def test_rate_limit_enforced(monkeypatch):
    _patch_l0_module(monkeypatch)
    client = _client(monkeypatch)
    hardening._RATE_PER_MIN = 1
    hardening._RATE_STATE.clear()

    r1 = client.post("/l0/analyse", json={"cve_id": "CVE-2021-0001"})
    r2 = client.post("/l0/analyse", json={"cve_id": "CVE-2021-0002"})

    assert r1.status_code == 200
    assert r2.status_code == 429


def test_failed_key_attempts_are_rate_limited(monkeypatch):
    client = _client(monkeypatch, VIGIL_API_KEYS=KEYS)
    hardening._RATE_PER_MIN = 2
    hardening._RATE_STATE.clear()

    codes = [client.get("/l6/watchlist", headers={"x-api-key": f"guess{i}"}).status_code for i in range(4)]
    assert codes == [401, 401, 429, 429]


def test_concurrency_cap_returns_503_for_llm_routes_only(monkeypatch):
    _patch_l0_module(monkeypatch)
    client = _client(monkeypatch)
    hardening._IN_FLIGHT = hardening._MAX_CONCURRENCY  # pretend every slot is busy

    r = client.post("/l0/analyse", json={"cve_id": CVE})
    assert r.status_code == 503
    assert r.headers["retry-after"] == "2"
    assert client.get("/l6/watchlist").status_code != 503  # reads are not capped


def test_concurrency_slot_is_released_after_each_request(monkeypatch):
    _patch_l0_module(monkeypatch)
    client = _client(monkeypatch)

    client.post("/l0/analyse", json={"cve_id": CVE})
    assert hardening._IN_FLIGHT == 0


# ─── request limits ──────────────────────────────────────────────────────────

def test_oversized_body_is_rejected_before_the_handler_runs(monkeypatch):
    calls = _patch_l0_module(monkeypatch)
    client = _client(monkeypatch)
    hardening._MAX_BODY_BYTES = 50

    r = client.post("/l0/analyse", json={"cve_id": CVE, "padding": "x" * 200})
    assert r.status_code == 413
    assert calls["n"] == 0


def test_upload_routes_get_a_larger_limit(monkeypatch):
    _patch_l0_module(monkeypatch)
    client = _client(monkeypatch)
    hardening._MAX_BODY_BYTES = 50
    hardening._MAX_UPLOAD_BYTES = 100_000

    r = client.post("/l4b/pdf", json={"content_base64": "x" * 500})
    assert r.status_code != 413


def test_chunked_body_without_length_is_rejected(monkeypatch):
    client = _client(monkeypatch)

    def body():
        yield b'{"cve_id": "CVE-2021-44228"}'

    r = client.post("/l0/analyse", content=body(), headers={"content-type": "application/json"})
    assert r.status_code == 411


@pytest.mark.parametrize("bad", ["CVE-1", "cve-2021-44228", "CVE-2021-44228; DROP TABLE x", "x" * 500, ""])
def test_malformed_cve_id_is_rejected(monkeypatch, bad):
    calls = _patch_l0_module(monkeypatch)
    client = _client(monkeypatch)

    assert client.post("/l0/analyse", json={"cve_id": bad}).status_code == 422
    assert calls["n"] == 0


def test_malformed_cve_id_in_path_is_rejected(monkeypatch):
    client = _client(monkeypatch)
    assert client.get("/l5/history/not-a-cve").status_code == 422
    assert client.delete("/l6/watchlist/not-a-cve").status_code == 422


# ─── CORS ────────────────────────────────────────────────────────────────────

def _preflight(client, origin):
    return client.options(
        "/l0/analyse",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "x-api-key",
        },
    )


def test_cors_allows_only_listed_origins(monkeypatch):
    client = _client(monkeypatch, VIGIL_API_KEYS=KEYS, VIGIL_CORS_ORIGINS="https://app.example.com")

    ok = _preflight(client, "https://app.example.com")
    assert ok.status_code == 200
    assert ok.headers["access-control-allow-origin"] == "https://app.example.com"
    assert "access-control-allow-origin" not in _preflight(client, "https://evil.example").headers


def test_cors_default_is_streamlit_in_dev_and_none_in_prod(monkeypatch):
    dev = _client(monkeypatch)
    assert _preflight(dev, "http://localhost:8501").headers["access-control-allow-origin"] == "http://localhost:8501"
    assert "access-control-allow-origin" not in _preflight(dev, "https://evil.example").headers

    prod = _client(monkeypatch, VIGIL_ENV="prod", VIGIL_API_KEYS=KEYS)
    assert "access-control-allow-origin" not in _preflight(prod, "http://localhost:8501").headers


def test_cors_wildcard_is_refused():
    with pytest.raises(ValueError):
        hardening.parse_cors_origins("*")


def test_401_responses_still_carry_cors_headers(monkeypatch):
    client = _client(monkeypatch, VIGIL_API_KEYS=KEYS, VIGIL_CORS_ORIGINS="https://app.example.com")
    r = client.get("/l6/watchlist", headers={"Origin": "https://app.example.com"})
    assert r.status_code == 401
    assert r.headers["access-control-allow-origin"] == "https://app.example.com"


# ─── cache ───────────────────────────────────────────────────────────────────

def test_response_cache_hit_on_second_identical_request(monkeypatch):
    calls = _patch_l0_module(monkeypatch)
    client = _client(monkeypatch)
    hardening._RATE_PER_MIN = 1000
    hardening._RATE_STATE.clear()
    hardening._CACHE._mem.clear()

    r1 = client.post("/l0/analyse", json={"cve_id": "CVE-2021-0003"})
    r2 = client.post("/l0/analyse", json={"cve_id": "CVE-2021-0003"})

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
