from __future__ import annotations

from pathlib import Path

import pytest


def test_mapping_doc_exists():
    path = Path("architectures/frameworks/MAPPING.md")
    assert path.exists()
    assert "LangGraph" in path.read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_langgraph_port_runs_or_degrades_gracefully(monkeypatch):
    from architectures.frameworks import a1_react_langgraph as lg

    def _boom():
        raise ImportError("langgraph missing")

    monkeypatch.setattr(lg, "build_graph", _boom)

    out = await lg.analyse_cve("CVE-2021-44228")
    assert out["cve_id"] == "CVE-2021-44228"
    assert "verdict" in out
