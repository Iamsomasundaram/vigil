"""Architecture pages A1-A4."""

import httpx
import streamlit as st

from common import (
    API_BASE,
    cost_line,
)


# ─── A1: ReAct ────────────────────────────────────────────────────────────────

def render_a1() -> None:
    st.title("A1 — ReAct")
    st.markdown(
        "**ReAct** (Reasoning + Acting) makes the agent's thought process visible. "
        "Before every tool call the agent writes a *Thought* explaining its reasoning. "
        "The result is a full **Thought → Action → Observation** trace — not just what "
        "the agent did, but *why* it did it."
    )

    st.info(
        "**How this differs from L4 (Tool Use)**  \n"
        "L4 also uses tools, but the reasoning is hidden inside the model. "
        "ReAct surfaces it as a first-class output you can read, debug, and audit.",
        icon="💡",
    )

    st.caption(
        "F7 bridge: see architectures/frameworks/a1_react_langgraph.py and "
        "architectures/frameworks/MAPPING.md for a direct hand-rolled ReAct -> LangGraph mapping."
    )

    with st.expander("Pattern diagram", expanded=False):
        st.markdown("""
```
┌─────────────────────────────────────────────────────────────────────┐
│  Thought  — Why do I need to do this? What am I trying to find out? │
│  Action   — Call a tool  (NVD · EPSS · CISA KEV)                    │
│  Observe  — Read the result                                         │
│  Thought  — What did I learn? What should I do next?                │
│  Action   — Call another tool (or conclude)                         │
│  Observe  — ...                                                     │
│  Answer   — Final report, grounded in all observations              │
└─────────────────────────────────────────────────────────────────────┘
```
**Tools available to the agent:**
- `fetch_nvd_data` — CVSS score, description, severity (NVD API)
- `fetch_epss_score` — exploitation probability 0–1 (EPSS API, updated daily)
- `check_cisa_kev` — is this CVE being actively exploited right now? (CISA KEV catalog)
        """)

    st.divider()

    cve_id = st.text_input("CVE ID", key="vigil_cve")

    if st.button("Run ReAct Investigation", type="primary"):
        with st.spinner("Agent is thinking and acting..."):
            resp = httpx.post(f"{API_BASE}/a1/analyse", json={"cve_id": cve_id}, timeout=120)

        if resp.status_code == 200:
            data  = resp.json()
            report = data["report"]
            trace  = data["reasoning_trace"]

            st.success("✅ Investigation complete")
            cost_line(data)

            # ── Reasoning trace ───────────────────────────────────────────────
            st.subheader("Reasoning Trace")
            st.caption("Every Thought → Action → Observation cycle the agent executed.")

            for step in trace:
                thought     = step.get("thought", "").strip()
                action      = step.get("action", "")
                args        = step.get("arguments", {})
                observation = step.get("observation", "")

                with st.expander(f"Step {step['step']} — {action}", expanded=True):
                    col_t, col_a, col_o = st.columns([2, 2, 3])
                    with col_t:
                        st.markdown("**Thought**")
                        st.markdown(
                            f"<div style='color:#94A3B8;font-size:0.9em'>{thought or '—'}</div>",
                            unsafe_allow_html=True,
                        )
                    with col_a:
                        st.markdown("**Action**")
                        st.code(f"{action}({', '.join(f'{k}={v}' for k, v in args.items())})", language="python")
                    with col_o:
                        st.markdown("**Observation**")
                        st.markdown(
                            f"<div style='color:#94A3B8;font-size:0.9em'>{observation}</div>",
                            unsafe_allow_html=True,
                        )

            # ── Final report ──────────────────────────────────────────────────
            st.divider()
            st.subheader("Final Report")

            severity = report.get("cvss_severity", "").upper()
            epss_pct = report.get("epss_score", 0) * 100
            kev = report.get("in_cisa_kev", False)

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("CVSS Score", f"{report.get('cvss_score', 'N/A')} ({severity})")
            c2.metric("EPSS", f"{epss_pct:.1f}%", help="Exploitation probability in next 30 days")
            c3.metric("CISA KEV", "🔴 YES" if kev else "🟢 No", help="Actively exploited in the wild?")
            c4.metric("Reasoning Steps", report.get("reasoning_steps", len(trace)))

            st.markdown(f"**Risk Verdict**  \n{report.get('risk_verdict', '')}")
            st.markdown(f"**Recommended Action**  \n{report.get('recommended_action', '')}")

            with st.expander("Full report JSON"):
                st.json(report)

        else:
            st.error(f"API error {resp.status_code}: {resp.text}")

# ─── A2: Plan-and-Execute ─────────────────────────────────────────────────────

def render_a2() -> None:
    st.title("A2 — Plan-and-Execute")
    st.markdown(
        "**Plan-and-Execute** strictly separates thinking from acting. "
        "The planner produces a complete investigation plan in one LLM call — "
        "before anything is executed. Then the executor runs each step independently."
    )

    st.info(
        "**Key insight**  \n"
        "You can inspect (and theoretically approve or modify) the plan *before* "
        "any tool is called. This is how you add human oversight checkpoints to an agentic workflow.",
        icon="💡",
    )

    with st.expander("Pattern diagram", expanded=False):
        st.markdown("""
```
PHASE 1 — PLAN  (one LLM call, no tools)
  Planner: "Here is my step-by-step investigation plan..."
    Step 1: [tool_call] fetch_nvd_data    — get CVSS & description
    Step 2: [tool_call] fetch_epss_score  — get exploitation probability
    Step 3: [tool_call] check_cisa_kev    — check active exploitation
    Step 4: [synthesise] write final report

PHASE 2 — EXECUTE  (one action per step)
  Executor runs each step in order, collecting observations.
  All observations feed the final synthesis.
```
        """)

    st.divider()

    cve_id = st.text_input("CVE ID", key="vigil_cve")

    if st.button("Run Plan-and-Execute", type="primary"):
        with st.spinner("Planning investigation..."):
            resp = httpx.post(f"{API_BASE}/a2/analyse", json={"cve_id": cve_id}, timeout=120)

        if resp.status_code == 200:
            data    = resp.json()
            plan    = data["plan"]
            exe_log = data["execution_log"]
            report  = data["report"]

            st.success("✅ Done")
            cost_line(data)

            # ── Plan ──────────────────────────────────────────────────────────
            st.subheader("Investigation Plan")
            st.caption(f"Goal: {plan.get('goal', '')}")
            st.caption(f"Planner reasoning: {plan.get('reasoning', '')}")

            for step in plan.get("steps", []):
                step_type = step.get("step_type", "")
                icon      = "🔧" if step_type == "tool_call" else "🧠"
                colour    = "#6366F1" if step_type == "tool_call" else "#10B981"
                tool_str  = f" → `{step['tool_name']}`" if step.get("tool_name") else ""
                st.markdown(
                    f"""<div style="background:#1E1E2E;border-left:3px solid {colour};
                                   padding:8px 12px;margin-bottom:6px;border-radius:4px">
                      <span style="color:{colour};font-weight:bold">{icon} Step {step['step']} [{step_type}]{tool_str}</span><br>
                      <span style="color:#94A3B8;font-size:0.9em">{step['description']}</span>
                    </div>""",
                    unsafe_allow_html=True,
                )

            # ── Execution log ──────────────────────────────────────────────────
            st.divider()
            st.subheader("Execution Log")

            for entry in exe_log:
                status  = entry.get("status", "ok")
                icon    = "✅" if status == "ok" else "❌"
                result  = entry.get("result", {})
                preview = ""
                if isinstance(result, dict) and "note" in result:
                    preview = result["note"]
                elif isinstance(result, dict) and "description" in result:
                    preview = result["description"][:120]
                elif isinstance(result, dict) and "error" in result:
                    preview = f"Error: {result['error']}"

                with st.expander(f"{icon} Step {entry['step']} — {entry['tool']}"):
                    if preview:
                        st.markdown(f"<div style='color:#94A3B8'>{preview}</div>", unsafe_allow_html=True)
                    if result and entry["tool"] != "synthesise":
                        st.json(result)

            # ── Final report ──────────────────────────────────────────────────
            st.divider()
            st.subheader("Final Report")

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("CVSS", f"{report.get('cvss_score')} ({report.get('cvss_severity')})")
            c2.metric("EPSS", f"{report.get('epss_score', 0) * 100:.1f}%")
            c3.metric("CISA KEV", "🔴 YES" if report.get("in_cisa_kev") else "🟢 No")
            c4.metric("Steps Run", report.get("steps_executed", len(exe_log)))

            st.markdown(f"**Risk Verdict**  \n{report.get('risk_verdict', '')}")
            st.markdown(f"**Recommended Action**  \n{report.get('recommended_action', '')}")

            with st.expander("Full report JSON"):
                st.json(report)
        else:
            st.error(f"API error {resp.status_code}: {resp.text}")

# ─── A3: Reflection ───────────────────────────────────────────────────────────

def render_a3() -> None:
    st.title("A3 — Reflection / Self-Critique")
    st.markdown(
        "**Reflection** makes the agent critique its own output before returning it. "
        "The agent produces a draft, an adversarial critic identifies problems, "
        "then a reviser produces an improved final report."
    )

    st.info(
        "**Key insight**  \n"
        "The draft and final report are both shown so you can see the quality improvement. "
        "The critique is the mechanism — compare what the critic found against what changed.",
        icon="💡",
    )

    with st.expander("Pattern diagram", expanded=False):
        st.markdown("""
```
PHASE 1 — RESEARCH
  Fetch NVD + EPSS + CISA KEV in parallel → write Draft Assessment

PHASE 2 — CRITIQUE  (adversarial self-review)
  Critic checks: unsupported claims · missing context · overstatements
               · vague recommendations · inconsistent severity

PHASE 3 — REVISE
  Reviser addresses every critique point → Final Report
  changes_from_draft records exactly what improved
```
        """)

    st.divider()

    cve_id = st.text_input("CVE ID", key="vigil_cve")

    if st.button("Run Reflection Analysis", type="primary"):
        with st.spinner("Researching, critiquing, and revising..."):
            resp = httpx.post(f"{API_BASE}/a3/analyse", json={"cve_id": cve_id}, timeout=120)

        if resp.status_code == 200:
            data     = resp.json()
            draft    = data["draft"]
            critique = data["critique"]
            report   = data["report"]

            st.success("✅ Done")
            cost_line(data)

            # ── Side-by-side: draft vs final ──────────────────────────────────
            st.subheader("Draft vs Final")
            col_d, col_f = st.columns(2)

            with col_d:
                st.markdown("**Draft Assessment**")
                st.markdown(
                    f"<div style='background:#1E1E2E;border-top:3px solid #FFA500;"
                    f"padding:12px;border-radius:6px;color:#94A3B8;font-size:0.9em'>"
                    f"CVSS {draft.get('cvss_score')} ({draft.get('cvss_severity')})<br>"
                    f"EPSS {draft.get('epss_score', 0) * 100:.1f}%<br>"
                    f"Confidence: {draft.get('confidence')}<br><br>"
                    f"{draft.get('risk_summary', '')}</div>",
                    unsafe_allow_html=True,
                )

            with col_f:
                st.markdown("**Final Report (after critique)**")
                st.markdown(
                    f"<div style='background:#1E1E2E;border-top:3px solid #21C354;"
                    f"padding:12px;border-radius:6px;color:#94A3B8;font-size:0.9em'>"
                    f"CVSS {report.get('cvss_score')} ({report.get('cvss_severity')})<br>"
                    f"EPSS {report.get('epss_score', 0) * 100:.1f}%<br>"
                    f"Confidence: {report.get('confidence')}<br><br>"
                    f"{report.get('risk_summary', '')}</div>",
                    unsafe_allow_html=True,
                )

            # ── Critique ──────────────────────────────────────────────────────
            st.divider()
            st.subheader("Critique")
            quality       = critique.get("overall_quality", "")
            needs_revision = critique.get("improvement_needed", False)

            c1, c2 = st.columns(2)
            c1.metric("Overall Quality", quality.upper())
            c2.metric("Revision Needed", "Yes" if needs_revision else "No")

            if critique.get("issues"):
                st.markdown("**Issues found:**")
                for issue in critique["issues"]:
                    st.markdown(f"- 🔴 {issue}")

            if critique.get("overstatements"):
                st.markdown("**Overstatements:**")
                for o in critique["overstatements"]:
                    st.markdown(f"- 🟡 {o}")

            if critique.get("missing_context"):
                st.markdown("**Missing context:**")
                for m in critique["missing_context"]:
                    st.markdown(f"- 🔵 {m}")

            # ── Changes made ──────────────────────────────────────────────────
            changes = report.get("changes_from_draft", [])
            if changes:
                st.divider()
                st.subheader("Improvements Made")
                for change in changes:
                    st.markdown(f"- ✅ {change}")

            # ── Final metrics ─────────────────────────────────────────────────
            st.divider()
            c1, c2, c3 = st.columns(3)
            c1.metric("CISA KEV", "🔴 YES" if report.get("in_cisa_kev") else "🟢 No")
            c2.metric("Patch Available", "Yes" if report.get("patch_available") else "No")
            c3.metric("Final Confidence", report.get("confidence", ""))
            st.markdown(f"**Recommended Action**  \n{report.get('recommended_action', '')}")

            with st.expander("Full JSON (all three stages)"):
                st.json(data)
        else:
            st.error(f"API error {resp.status_code}: {resp.text}")

# ─── A4: Multi-Agent ──────────────────────────────────────────────────────────

def render_a4() -> None:
    st.title("A4 — Multi-Agent")
    st.markdown(
        "**Multi-Agent** uses an orchestrator that dispatches three specialist agents "
        "in parallel. Each agent has its own role, system prompt, and tools. "
        "The orchestrator synthesises all three reports into a final verdict."
    )

    st.info(
        "**Key insight**  \n"
        "Compare agent reports side-by-side to see how the same CVE looks different "
        "depending on the lens (threat intel vs impact vs remediation). "
        "The orchestrator's job is to weigh those perspectives into a coherent whole.",
        icon="💡",
    )

    with st.expander("Pattern diagram", expanded=False):
        st.markdown("""
```
            ORCHESTRATOR
   "Investigate CVE-XXXX-XXXXX"
          ↙         ↓         ↘          ← dispatched in parallel
ThreatIntel    Impact      Remediation
  Agent        Agent         Agent
  (NVD +      (EPSS +       (NVD +
  CISA KEV)    NVD)         CISA KEV)
          ↘         ↓         ↙          ← reports collected
            ORCHESTRATOR
         synthesises final verdict
```
        """)

    st.divider()

    cve_id = st.text_input("CVE ID", key="vigil_cve")

    if st.button("Run Multi-Agent Analysis", type="primary"):
        with st.spinner("Three agents working in parallel..."):
            resp = httpx.post(f"{API_BASE}/a4/analyse", json={"cve_id": cve_id}, timeout=180)

        if resp.status_code == 200:
            data         = resp.json()
            agent_reports = data["agent_reports"]
            tool_log     = data["tool_log"]
            report       = data["report"]

            threat      = agent_reports.get("threat_intel", {})
            impact      = agent_reports.get("impact_assessment", {})
            remediation = agent_reports.get("patch_remediation", {})

            st.success("✅ Done")
            cost_line(data)

            # ── Agent reports ─────────────────────────────────────────────────
            st.subheader("Agent Reports")
            col_t, col_i, col_r = st.columns(3)

            with col_t:
                st.markdown(
                    "<div style='color:#6366F1;font-weight:bold'>🔍 Threat Intel</div>",
                    unsafe_allow_html=True,
                )
                st.metric("CVSS", f"{threat.get('cvss_score')} ({threat.get('cvss_severity')})")
                st.metric("Active Exploit", "🔴 YES" if threat.get("actively_exploited") else "🟢 No")
                st.markdown(f"<div style='color:#94A3B8;font-size:0.85em'>{threat.get('threat_summary', '')}</div>", unsafe_allow_html=True)

            with col_i:
                st.markdown(
                    "<div style='color:#F59E0B;font-weight:bold'>📊 Impact Assessment</div>",
                    unsafe_allow_html=True,
                )
                st.metric("EPSS", f"{impact.get('epss_score', 0) * 100:.1f}%")
                st.metric("Likely Exploited", "🔴 YES" if impact.get("exploitation_likely") else "🟢 No")
                st.markdown(f"<div style='color:#94A3B8;font-size:0.85em'>{impact.get('impact_summary', '')}</div>", unsafe_allow_html=True)

            with col_r:
                st.markdown(
                    "<div style='color:#10B981;font-weight:bold'>🔧 Patch & Remediation</div>",
                    unsafe_allow_html=True,
                )
                st.metric("Patch Available", "Yes" if remediation.get("patch_available") else "No")
                st.metric("Urgency", remediation.get("urgency", "").upper())
                st.markdown(f"<div style='color:#94A3B8;font-size:0.85em'>{remediation.get('remediation_summary', '')}</div>", unsafe_allow_html=True)

            # ── Tool call log ──────────────────────────────────────────────────
            if tool_log:
                st.divider()
                with st.expander(f"Tool calls ({len(tool_log)} total across all agents)"):
                    for entry in tool_log:
                        agent  = entry.get("agent", "")
                        tool   = entry.get("tool", "")
                        result = entry.get("result", {})
                        note   = result.get("note") or result.get("description", "")[:100] if isinstance(result, dict) else ""
                        st.markdown(f"**[{agent}]** `{tool}` → {note or '(see JSON)'}")

            # ── Orchestrator synthesis ─────────────────────────────────────────
            st.divider()
            st.subheader("Orchestrator Synthesis")


            c1, c2, c3, c4 = st.columns(4)
            c1.metric("CVSS", f"{report.get('cvss_score')} ({report.get('cvss_severity')})")
            c2.metric("EPSS", f"{report.get('epss_score', 0) * 100:.1f}%")
            c3.metric("CISA KEV", "🔴 YES" if report.get("actively_exploited") else "🟢 No")
            c4.metric("Overall Urgency", report.get("overall_urgency", "").upper())

            st.markdown(f"**Risk Verdict**  \n{report.get('risk_verdict', '')}")
            st.markdown(f"**Recommended Action**  \n{report.get('recommended_action', '')}")
            st.caption(f"Agents consulted: {', '.join(report.get('agents_consulted', []))}")

            with st.expander("Full JSON (all agents)"):
                st.json(data)
        else:
            st.error(f"API error {resp.status_code}: {resp.text}")
