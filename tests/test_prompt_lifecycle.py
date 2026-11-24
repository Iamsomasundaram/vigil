from __future__ import annotations

from levels.foundations.prompt_lifecycle import compare_versions, list_versions


def test_list_versions_returns_entries():
    versions = list_versions("data/prompts/f14_prompt_versions.json")
    assert len(versions) >= 2
    assert any(v["id"] == "v1" for v in versions)


def test_compare_versions_reports_winner_or_tie():
    out = compare_versions(
        version_a="v1",
        version_b="v2",
        items=["CVE-2021-44228", "CVE-2023-44487"],
        path="data/prompts/f14_prompt_versions.json",
    )

    assert out["overall_winner"] in {"a", "b", "tie"}
    assert len(out["per_item"]) == 2
    assert "a_avg_quality" in out["summary"]
