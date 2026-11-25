"""Theme track T1 (incident response ops)."""

import streamlit as st

from common import (
    api,
    badge,
    concept_box,
    learner_coach,
    learner_flow,
    lesson_objective,
    result_hint,
    severity_colour,
)


# ─── T1 ───────────────────────────────────────────────────────────────────────

def render_t1_incident() -> None:
    st.title("T1 — Incident Response Ops")
    lesson_objective("T1", "Transfer agentic patterns from CVE analysis to production incident triage.", "you can classify urgency and produce a structured first-hour response plan")

    concept_box(
        title="Same agent patterns, new domain",
        what="Use alert text plus service context to classify severity and route the response track.",
        why="This proves the learning stack is portable beyond CVEs into real SRE and incident workflows.",
        key_idea="alert signals -> severity/track -> immediate actions and escalation targets",
    )
    learner_flow(
        "T1",
        "Analyse incident",
        "severity, track, urgency, and action ordering",
        "Repeat with different incidents to stress-test routing",
    )
    learner_coach(
        "Keep one alert text constant while toggling customer impact.",
        "Read reasoning and escalation targets, not severity alone.",
        "Treating all degraded-service incidents as critical without context.",
    )

    c1, c2 = st.columns(2)
    alert_text = c1.text_area(
        "Incident alert text",
        value="Payment API error rate surged; checkout failures in two regions; possible data exfiltration indicators.",
        key="t1_alert_text",
        height=140,
    )
    service_name = c2.text_input("Service name", value="payments-api", key="t1_service")

    c3, c4 = st.columns(2)
    customer_impact = c3.checkbox("Customer impact observed", value=True, key="t1_customer_impact")
    signals_csv = c4.text_input(
        "Signals (comma-separated)",
        value="latency,error rate,checkout failures",
        key="t1_signals",
    )

    if st.button("Analyse incident", type="primary", key="t1_run"):
        signals = [s.strip() for s in signals_csv.split(",") if s.strip()]
        with st.spinner("Classifying incident severity and response track…"):
            data = api(
                "POST",
                "/themes/incident/analyse",
                json={
                    "alert_text": alert_text,
                    "service_name": service_name,
                    "customer_impact": customer_impact,
                    "signals": signals,
                },
            )

        if data:
            rep = data.get("report", {})
            sev = rep.get("severity", "Medium")
            c1m, c2m, c3m, c4m = st.columns(4)
            c1m.markdown(
                f"**Severity**<br>{badge(sev, severity_colour(sev))}",
                unsafe_allow_html=True,
            )
            c2m.metric("Track", rep.get("track", "?"))
            c3m.metric("Urgency", f"{rep.get('urgency_minutes', '?')} min")
            c4m.metric("Elapsed", f"{data.get('elapsed_ms', 0)} ms")

            st.markdown(f"**Summary:** {rep.get('summary', '')}")
            st.markdown(f"**Likely domains:** {', '.join(rep.get('likely_domains', []))}")

            st.markdown("### Immediate actions")
            for i, action in enumerate(rep.get("immediate_actions", []), 1):
                st.markdown(f"{i}. {action}")

            st.markdown("### Escalation targets")
            for target in rep.get("escalation_targets", []):
                st.markdown(f"- {target}")

            result_hint("Interpretation", rep.get("reasoning", "Review alert quality and incident context."))
