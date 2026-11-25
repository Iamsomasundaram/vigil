"""Core levels L0-L3."""

import streamlit as st

from common import (
    api,
    badge,
    concept_box,
    cost_line,
    cve_input,
    learner_coach,
    learner_flow,
    lesson_objective,
    result_hint,
    severity_colour,
    try_next_cve,
    under_the_hood,
)


# ─── L0 ───────────────────────────────────────────────────────────────────────

def render_l0() -> None:
    st.title("L0 — Single LLM Call")
    lesson_objective("L0", "Understand the baseline behavior of one prompt and one response.", "you can explain why this output is easy for humans but hard for automation")

    concept_box(
        title="The simplest possible AI interaction",
        what="One system prompt + one user message → one free-form text response.",
        why="Every agentic system, no matter how complex, is built on this primitive. "
            "Understanding it deeply before adding structure is essential.",
        key_idea="client.chat.completions.create(messages=[system, user]) → text string",
    )
    learner_flow(
        "L0",
        "Ask the model",
        "free-form text quality, coverage gaps, and ambiguity",
        "L1 to see how structure fixes these limits",
    )
    learner_coach(
        "Use the default CVE first so you can compare later pages on the same input.",
        "Focus on answer quality and whether key facts are explicit or vague.",
        "Treating fluent text as reliable structured truth.",
    )

    cve_id = cve_input("l0_cve")

    if st.button("Ask the model", type="primary", key="l0_run"):
        with st.spinner("Calling the LLM…"):
            data = api("POST", "/l0/analyse", json={"cve_id": cve_id})

        if data:
            st.success("✅ Done")
            cost_line(data)
            result_hint("What this means", "You got a human-readable answer, but it is unstructured text. Automation is hard at this stage.")
            st.markdown("### Response")
            st.markdown(
                f'<div style="background:#1E1E2E;padding:20px;border-radius:6px;'
                f'color:#E2E8F0;line-height:1.7">{data["explanation"]}</div>',
                unsafe_allow_html=True,
            )

            under_the_hood(
                code_snippet="""\
response = client.chat.completions.create(
    model=MODEL,
    messages=[
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user",   "content": f"Explain {cve_id}..."},
    ],
    temperature=0.2,
    max_tokens=600,
)
return response.choices[0].message.content  # plain string""",
                explanation="One API call. The output is unstructured text — great for humans, "
                            "unreliable for code to process. L1 solves this with structured output.",
            )
            try_next_cve("l0")

# ─── L1 ───────────────────────────────────────────────────────────────────────

def render_l1() -> None:
    st.title("L1 — Prompt Chain")
    lesson_objective("L1", "See how decomposing one big task into steps improves reliability.", "you can point to what each step contributes to final quality")

    concept_box(
        title="Three focused calls, each building on the last",
        what="Step 1 summarises the CVE. Step 2 assesses risk using step 1's output. "
             "Step 3 writes a remediation plan using steps 1+2.",
        why="One prompt trying to do all three produces mediocre results for all three. "
            "Chaining lets each step give its full attention to one job.",
        key_idea="summary = step1(cve)  →  risk = step2(summary)  →  plan = step3(summary, risk)",
    )
    learner_flow(
        "L1",
        "Run chain",
        "how each step gets more specific and machine-usable",
        "L2 for speed and specialization via parallelism",
    )
    learner_coach(
        "Run with the same CVE you used in L0 to make quality differences obvious.",
        "Check if step outputs become progressively more actionable.",
        "Assuming more tokens always means better output rather than better structure.",
    )

    cve_id = cve_input("l1_cve")

    if st.button("Run chain", type="primary", key="l1_run"):
        with st.spinner("Running 3-step chain… (each step is a separate LLM call)"):
            data = api("POST", "/l1/analyse", json={"cve_id": cve_id})

        if data:
            st.success("✅ All 3 steps completed")
            cost_line(data)
            result_hint("What changed from L0", "Output is now typed and decomposed by task, which makes downstream logic reliable.", tone="success")

            steps = data.get("steps", {})

            # Step 1
            with st.expander("📋 Step 1 — CVE Summary", expanded=True):
                s = steps.get("1_summary", {})
                col1, col2, col3 = st.columns(3)
                sev_colour = severity_colour(s.get("severity", ""))
                col1.metric("CVSS Score", s.get("cvss_score", "–"))
                col2.markdown(
                    f"**Severity**<br>{badge(s.get('severity','?'), sev_colour)}",
                    unsafe_allow_html=True,
                )
                col3.markdown(f"**Auth required**<br>{'Yes' if s.get('authentication_required') else 'No'}", unsafe_allow_html=True)
                st.markdown(f"**{s.get('affected_product','?')}** — {s.get('one_line_description','')}")
                st.caption(f"Attack vector: {s.get('attack_vector','?')} | Versions: {', '.join(s.get('affected_versions', [])[:5])}{'…' if len(s.get('affected_versions',[])) > 5 else ''}")

            # Step 2
            with st.expander("⚠️ Step 2 — Risk Assessment", expanded=True):
                r = steps.get("2_risk", {})
                col1, col2 = st.columns(2)
                col1.metric("Risk Score", f"{r.get('risk_score','?')}/10")
                col2.markdown(f"**Urgency**<br>`{r.get('urgency','?')}`", unsafe_allow_html=True)
                st.markdown(f"**Exploitability:** {r.get('exploitability_summary','')}")
                st.markdown(f"**Potential damage:** {r.get('potential_damage_summary','')}")
                if r.get("should_escalate_to_management"):
                    st.error("🔺 Escalate to management")

            # Step 3
            with st.expander("🔧 Step 3 — Remediation Plan", expanded=True):
                p = steps.get("3_remediation", {})
                col1, col2 = st.columns(2)
                col1.markdown(
                    f"**Patch:** {'✅ ' + (p.get('patch_version') or 'available') if p.get('patch_available') else '❌ Not yet available'}"
                )
                col2.metric("Effort", p.get("estimated_effort", "?"))

                st.markdown("**Immediate actions (next hour):**")
                for a in p.get("immediate_actions", []):
                    st.markdown(f"- 🔴 {a}")
                st.markdown("**Short-term actions:**")
                for a in p.get("short_term_actions", []):
                    st.markdown(f"- 🟡 {a}")
                st.info(f"**Rollback plan:** {p.get('rollback_plan','')}")

            under_the_hood(
                code_snippet="""\
summary = step1_summarise(cve_id)          # → CVESummary object
risk    = step2_assess_risk(summary)       # receives step 1 output
plan    = step3_remediation(summary, risk) # receives step 1 + 2 outputs

# Each step uses structured output — Pydantic validates the JSON:
# response_format={"type":"json_schema","json_schema":{...}}""",
                explanation="Each step returns a typed Pydantic object, not free text. "
                            "step2 knows the CVSS score from step1. step3 knows the urgency from step2. "
                            "This context accumulation is what makes the plan actually tailored.",
            )
            try_next_cve("l1")

# ─── L2 ───────────────────────────────────────────────────────────────────────

def render_l2() -> None:
    st.title("L2 — Parallel Fan-out")
    lesson_objective("L2", "Learn concurrency by comparing specialist breadth and latency.", "you can explain why parallel fan-out is faster than sequential pipelines")

    concept_box(
        title="Four specialist agents running simultaneously",
        what="Four agents — Exploitability, Impact, Patch, Business — all start at the same time "
             "via asyncio.gather(). A moderator then synthesises their reports.",
        why="Sequential (L1-style): 4 × 3s = 12s. Parallel (this level): max(3s, 3s, 3s, 3s) = 3s. "
            "At scale this difference is not optional — it's mandatory.",
        key_idea="results = await asyncio.gather(agent1(), agent2(), agent3(), agent4())",
    )
    learner_flow(
        "L2",
        "Run parallel agents",
        "specialist diversity plus lower end-to-end latency",
        "L3 for dynamic routing to avoid unnecessary work",
    )
    learner_coach(
        "Use a CVE with rich context (Log4Shell works well) so all specialists have signal.",
        "Read each specialist first, then the moderator as synthesis.",
        "Reading only the final verdict and skipping specialist disagreement.",
    )

    cve_id = cve_input("l2_cve")

    if st.button("Run parallel agents", type="primary", key="l2_run"):
        with st.spinner("4 agents running in parallel + moderator synthesis…"):
            data = api("POST", "/l2/analyse", json={"cve_id": cve_id})

        if data:
            st.success("✅ 4 agents + moderator complete")
            cost_line(data)
            result_hint("Interpretation", "Each agent gives a partial truth; the moderator is the synthesis layer, not a replacement for specialists.")
            st.caption("Compare elapsed time to L1's sequential run — parallel is almost always faster.")

            reports = data.get("agent_reports", {})
            verdict = data.get("verdict", {})

            # Show 4 agent cards
            st.markdown("### Agent Reports (ran in parallel)")
            cols = st.columns(4)
            agent_icons = {
                "Exploitability Agent": "⚔️",
                "Impact Agent":         "💥",
                "Patch Agent":          "🩹",
                "Business Impact Agent":"💼",
            }
            for col, (name, report) in zip(cols, reports.items()):
                with col:
                    icon = agent_icons.get(name, "🤖")
                    st.markdown(f"**{icon} {name.replace(' Agent','')}**")
                    for k, v in report.items():
                        if k == "key_finding":
                            continue
                        label = k.replace("_", " ").title()
                        val = ", ".join(str(x) for x in v) if isinstance(v, list) else str(v)
                        st.caption(f"**{label}:** {val}")
                    st.info(report.get("key_finding", ""))

            # Moderator verdict
            st.markdown("### Moderator Verdict")
            priority = verdict.get("overall_priority", "?")
            col1, col2, col3 = st.columns(3)
            col1.markdown(
                f"**Priority**<br>{badge(priority, severity_colour(priority))}",
                unsafe_allow_html=True,
            )
            col2.metric("Patch within", f"{verdict.get('recommended_sla_days','?')} days")
            col3.metric("Confidence", verdict.get("confidence", "?"))

            st.markdown(f"> {verdict.get('executive_summary','')}")
            st.markdown("**Top 3 actions:**")
            for i, action in enumerate(verdict.get("top_three_actions", []), 1):
                st.markdown(f"**{i}.** {action}")

            under_the_hood(
                code_snippet="""\
results = await asyncio.gather(
    run_agent(AGENTS[0], cve_id),  # Exploitability
    run_agent(AGENTS[1], cve_id),  # Impact
    run_agent(AGENTS[2], cve_id),  # Patch
    run_agent(AGENTS[3], cve_id),  # Business
)
# All four start immediately. Each yields control while waiting for the API.
# Total time ≈ slowest single call, not the sum of all calls.""",
                explanation="asyncio.gather() is the key primitive. Without await, each call blocks "
                            "the thread. With await, Python switches to the next coroutine while "
                            "waiting for the API response — real concurrency with one thread.",
            )
            try_next_cve("l2")

# ─── L3 ───────────────────────────────────────────────────────────────────────

def render_l3() -> None:
    st.title("L3 — Conditional Routing")
    lesson_objective("L3", "Understand AI-driven control flow and its operational impact.", "you can justify whether the selected track and urgency make sense")

    concept_box(
        title="The LLM decides which pipeline to run",
        what="A router agent classifies the CVE into one of four tracks. "
             "The track name is used as a dict key to dispatch to the right handler function.",
        why="Not every CVE needs a full L2 run. A CVSS 2.0 info-leak doesn't need the same "
            "response as Log4Shell. Routing saves cost and latency for low-priority items.",
        key_idea='handler = TRACK_HANDLERS[routing.track]  # LLM output drives Python control flow',
    )
    learner_flow(
        "L3",
        "Route and analyse",
        "selected track, urgency hours, and confidence",
        "L4 for live external grounding",
    )
    learner_coach(
        "Try two very different CVEs and compare track selection.",
        "Inspect routing reason before reading the track output details.",
        "Treating confidence as proof; confidence is a signal, not certainty.",
    )

    TRACK_COLOURS = {
        "critical_response":  "#FF4B4B",
        "standard_patch":     "#FFA500",
        "low_risk_monitor":   "#21C354",
        "needs_human_review": "#C77DFF",
    }
    TRACK_LABELS = {
        "critical_response":  "🚨 CRITICAL RESPONSE",
        "standard_patch":     "🩹 STANDARD PATCH",
        "low_risk_monitor":   "👁️ LOW RISK — MONITOR",
        "needs_human_review": "🧑‍💼 HUMAN REVIEW REQUIRED",
    }

    cve_id = cve_input("l3_cve")

    if st.button("Route and analyse", type="primary", key="l3_run"):
        with st.spinner("Router classifying CVE, then running the matched track…"):
            data = api("POST", "/l3/analyse", json={"cve_id": cve_id})

        if data:
            routing = data.get("routing", {})
            result  = data.get("result", {})
            track   = routing.get("track", "")
            colour  = TRACK_COLOURS.get(track, "#888")
            label   = TRACK_LABELS.get(track, track)

            st.success("✅ Done")
            cost_line(data)
            result_hint("Interpretation", "Routing is a cost and latency control decision; wrong routing can be as harmful as wrong analysis.", tone="warning")

            # Routing decision — show prominently
            st.markdown("### Routing Decision")
            st.markdown(
                f'<div style="background:{colour}22;border:2px solid {colour};'
                f'padding:16px;border-radius:8px;margin-bottom:16px">'
                f'<div style="font-size:1.4em;font-weight:bold;color:{colour}">{label}</div>'
                f'<div style="margin-top:8px;color:#E2E8F0">{routing.get("reason","")}</div>'
                f'<div style="margin-top:6px;color:#94A3B8">Act within: {routing.get("urgency_hours","?")}h  '
                f'· Confidence: {routing.get("confidence","?")}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

            # Track result
            st.markdown("### Track Result")
            for k, v in result.items():
                label_text = k.replace("_", " ").title()
                if isinstance(v, list):
                    st.markdown(f"**{label_text}:**")
                    for item in v:
                        st.markdown(f"  - {item}")
                elif isinstance(v, bool):
                    st.markdown(f"**{label_text}:** {'✅ Yes' if v else '❌ No'}")
                else:
                    st.markdown(f"**{label_text}:** {v}")

            under_the_hood(
                code_snippet="""\
TRACK_HANDLERS = {
    "critical_response":  handle_critical,
    "standard_patch":     handle_standard_patch,
    "low_risk_monitor":   handle_low_risk,
    "needs_human_review": handle_human_review,
}

routing = await run_router(cve_id)         # LLM returns RoutingDecision
handler = TRACK_HANDLERS[routing.track]   # dict lookup — no if/elif chain
result  = await handler(cve_id, routing)  # run the matched pipeline""",
                explanation="The LLM's structured output (a Literal['critical_response',...] field) "
                            "is used directly as a Python dict key. The AI makes a judgment call; "
                            "the code executes it deterministically. That's the router pattern.",
            )
            try_next_cve("l3")
