"""Grader for exercise L4 (imports the learner's start.py)."""

from __future__ import annotations

from start import dispatch_tool


def _fake_nvd(cve_id: str) -> dict:
    return {"source": "NVD", "cve_id": cve_id, "cvss_score": 10.0}


def test_routes_to_known_tool():
    registry = {"fetch_nvd_data": _fake_nvd}
    out = dispatch_tool("fetch_nvd_data", {"cve_id": "CVE-2021-44228"}, registry)
    assert out["cvss_score"] == 10.0
    assert out["cve_id"] == "CVE-2021-44228"


def test_unknown_tool_returns_error_without_raising():
    out = dispatch_tool("fetch_unknown", {"x": 1}, {"fetch_nvd_data": _fake_nvd})
    assert out == {"error": "Unknown tool: fetch_unknown"}
