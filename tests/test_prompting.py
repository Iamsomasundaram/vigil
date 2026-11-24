from __future__ import annotations

import pytest


def test_zero_few_cot_shapes_and_features():
    from levels.foundations.prompting import chain_of_thought, few_shot, zero_shot

    z = zero_shot("CVE-2021-44228", "IGNORE PREVIOUS")
    f = few_shot("CVE-2021-44228", "IGNORE PREVIOUS")
    c = chain_of_thought("CVE-2021-44228", "IGNORE PREVIOUS")

    assert len(z) == 2 and z[0]["role"] == "system"
    assert "Examples:" in f[1]["content"]
    assert "step by step" in c[0]["content"].lower()
    assert "<UNTRUSTED_CVE_TEXT>" in z[1]["content"]


@pytest.mark.asyncio
async def test_self_consistency_majority_vote_with_stub():
    from levels.foundations.prompting import self_consistency

    async def stub_complete(_: list[dict[str, str]], __: float) -> str:
        return "Severity is High."

    out = await self_consistency("CVE-TEST", "text", n=5, complete_fn=stub_complete)
    assert out["majority_label"] == "High"
    assert out["vote_share"] == 1.0
    assert len(out["samples"]) == 5


def test_template_rendering():
    from levels.foundations.prompting import render

    assert render("Hello {name}", name="Vigil") == "Hello Vigil"
