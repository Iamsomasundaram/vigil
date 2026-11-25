from __future__ import annotations

from levels.foundations.responsible_ai import fairness_report, moderate_text, responsible_ai_report


def test_moderate_text_flags_harassment():
    out = moderate_text("You stupid loser")
    assert out["flagged"] is True
    assert "harassment" in out["categories"]
    assert out["action"] == "block"


def test_moderate_text_allows_clean():
    out = moderate_text("This CVE analysis is helpful and clear")
    assert out["flagged"] is False
    assert out["action"] == "allow"


def test_fairness_report_detects_disparate_impact():
    outcomes = [
        {"group": "a", "positive": True},
        {"group": "a", "positive": True},
        {"group": "b", "positive": False},
        {"group": "b", "positive": False},
    ]
    out = fairness_report(outcomes)
    assert out["disparate_impact_ratio"] < 0.8
    assert out["passes_80pct_rule"] is False


def test_responsible_ai_report_safe_to_ship_flag():
    out = responsible_ai_report(
        texts=["all good here"],
        outcomes=[{"group": "a", "positive": True}, {"group": "b", "positive": True}],
    )
    assert out["flagged_texts"] == 0
    assert out["safe_to_ship"] is True


def test_kill_the_process_is_not_flagged_as_hate():
    from levels.foundations.responsible_ai import moderate_text

    assert not moderate_text("kill the process and restart the worker")["flagged"]
    assert moderate_text("exterminate them")["flagged"]
