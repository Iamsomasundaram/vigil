from __future__ import annotations

import json

import pytest


def test_list_tools_contains_nvd_and_epss():
    from vigil_mcp.vigil_server import list_tools

    names = {t["name"] for t in list_tools()}
    assert {"fetch_nvd_data", "fetch_epss_score"} <= names


@pytest.mark.asyncio
async def test_call_tool_unknown_returns_error():
    from vigil_mcp.vigil_server import call_tool

    out = json.loads(await call_tool("does_not_exist", {}))
    assert "error" in out


@pytest.mark.asyncio
async def test_call_tool_stubbed_epss(monkeypatch):
    from vigil_mcp import vigil_server

    async def fake_epss(cve_id: str):
        return {"source": "EPSS", "cve_id": cve_id, "score": 0.77, "percentile": 0.98}

    monkeypatch.setattr(vigil_server, "_fetch_epss_score", fake_epss)
    out = json.loads(await vigil_server.call_tool("fetch_epss_score", {"cve_id": "CVE-X"}))
    assert out["score"] == 0.77
