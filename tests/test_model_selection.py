from __future__ import annotations

from levels.foundations.model_selection import claude_tiers, recommend_model


def test_low_complexity_latency_recommends_haiku():
    out = recommend_model(task_complexity="low", latency_sensitive=True)
    assert out["recommended"] == "haiku"


def test_high_complexity_high_stakes_recommends_opus():
    out = recommend_model(task_complexity="high", high_stakes=True)
    assert out["recommended"] == "opus"


def test_medium_defaults_to_sonnet():
    out = recommend_model(task_complexity="medium")
    assert out["recommended"] == "sonnet"


def test_claude_tiers_catalog():
    tiers = claude_tiers()
    names = {t["tier"] for t in tiers}
    assert {"haiku", "sonnet", "opus"} <= names
