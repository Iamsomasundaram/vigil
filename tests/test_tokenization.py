from __future__ import annotations

import pytest


def test_count_tokens_matches_tiktoken_when_available():
    tiktoken = pytest.importorskip("tiktoken")
    from levels.foundations.tokenization import count_tokens

    text = "CVE-2021-44228 remote code execution"
    enc = tiktoken.encoding_for_model("gpt-4o-mini")
    assert count_tokens(text, model="gpt-4o-mini") == len(enc.encode(text))


def test_budget_report_flags_over_limit():
    from vigil.pricing import budget_report

    out = budget_report(model="gpt-4o-mini", prompt_tokens=999_999, completion_tokens=0)
    assert out["over_limit"] is True
    assert out["pct_of_context"] > 100.0


def test_tokenize_report_contains_samples():
    pytest.importorskip("tiktoken")
    from levels.foundations.tokenization import tokenize_report

    rep = tokenize_report("log4shell", model="gpt-4o-mini")
    assert rep["token_count"] >= 1
    assert isinstance(rep["sample_tokens"], list)
