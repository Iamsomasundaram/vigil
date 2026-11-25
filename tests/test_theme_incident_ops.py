from __future__ import annotations

from levels.themes.incident_ops import analyse_incident


def test_incident_ops_critical_track_when_customer_impact_and_severe_terms():
    rep = analyse_incident(
        alert_text="Payment failures observed with possible data breach indicators",
        service_name="payments-api",
        customer_impact=True,
        signals=["latency", "error rate"],
    )

    assert rep.severity == "Critical"
    assert rep.track == "containment"
    assert rep.urgency_minutes == 15


def test_incident_ops_mitigation_track_for_degradation_without_breach_terms():
    rep = analyse_incident(
        alert_text="Elevated timeout and degraded response times",
        service_name="auth-api",
        customer_impact=False,
        signals=["auth failure", "latency"],
    )

    assert rep.severity == "High"
    assert rep.track == "mitigation"
    assert "identity" in rep.likely_domains


def test_incident_ops_monitor_track_for_low_signal_alerts():
    rep = analyse_incident(
        alert_text="Minor warning in background worker logs",
        service_name="worker",
        customer_impact=False,
        signals=["warning"],
    )

    assert rep.severity == "Medium"
    assert rep.track == "monitor"
    assert rep.urgency_minutes == 240


def test_rce_term_does_not_match_inside_other_words():
    from levels.themes.incident_ops import _CRITICAL_TERMS, _contains_any

    assert not _contains_any("resource exhaustion on the worker pool", _CRITICAL_TERMS)
    assert _contains_any("suspected RCE on the gateway", _CRITICAL_TERMS)
