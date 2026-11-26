"""Core levels L4, L4b, L5, L6."""

import base64

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


# ─── L4 ───────────────────────────────────────────────────────────────────────

def render_l4() -> None:
    st.title("L4 — Tool Use")
    lesson_objective("L4", "Learn grounding: trust comes from tool evidence, not model fluency.", "you can trace final claims back to NVD/EPSS tool outputs")

    concept_box(
        title="Agent calls real external APIs — analysis grounded in live data",
        what="The agent is given two tools: fetch_nvd_data and fetch_epss_score. "
             "It decides when to call them, reads the results, and builds its analysis from real data.",
        why="Without tools, the model relies on training memory — which has a cutoff date "
            "and can hallucinate scores. With tools, every fact is traceable to an API call.",
        key_idea="while response has tool_calls: execute_tool() → append result → call LLM again",
    )
    learner_flow(
        "L4",
        "Fetch live data and analyse",
        "tool call log first, then final grounded recommendation",
        "L5 to add temporal memory and feedback",
    )
    learner_coach(
        "Keep CVE constant and compare L3 vs L4 behavior.",
        "Read tool logs first, then verify the final analysis references those facts.",
        "Skipping tool logs and trusting summary text by default.",
    )

    cve_id = cve_input("l4_cve")

    if st.button("Fetch live data and analyse", type="primary", key="l4_run"):
        with st.spinner("Agent calling NVD and EPSS APIs, then synthesising…"):
            data = api("POST", "/l4/analyse", json={"cve_id": cve_id})

        if data:
            analysis   = data.get("analysis", {})
            tool_calls = data.get("tool_calls", [])

            st.success(f"✅ Done — {len(tool_calls)} real API call(s) made")
            cost_line(data)
            result_hint("Interpretation", "Trust the analysis only to the extent the tool log supports it. The log is your audit trail.", tone="success")

            # Tool call trace — show what the agent actually fetched
            st.markdown("### Tool Call Log")
            st.caption("These are real external API calls made by the agent during this analysis.")
            for i, tc in enumerate(tool_calls, 1):
                result = tc.get("result", {})
                with st.expander(
                    f"Tool {i}: `{tc['tool']}({tc['arguments'].get('cve_id','?')})`",
                    expanded=True,
                ):
                    if "error" in result:
                        st.error(f"Error: {result['error']}")
                    else:
                        for k, v in result.items():
                            if k not in ("source", "cve_id"):
                                st.markdown(f"**{k.replace('_',' ').title()}:** `{v}`")

            # Grounded analysis
            st.markdown("### Grounded Analysis")
            st.caption("All values below came from the tool calls above — not from model training memory.")

            sev    = analysis.get("cvss_severity", "?").upper()
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("CVSS Score", analysis.get("cvss_score", "?"))
            col2.markdown(
                f"**Severity**<br>{badge(sev, severity_colour(sev))}",
                unsafe_allow_html=True,
            )

            epss = analysis.get("epss_score", 0)
            epss_pct = epss * 100
            col3.metric("EPSS Score", f"{epss:.4f}", delta=f"{epss_pct:.1f}% exploitation probability")
            col4.metric("EPSS Percentile", f"{analysis.get('epss_percentile',0)*100:.0f}th")

            st.markdown("**Description (verbatim from NVD):**")
            st.info(analysis.get("description", ""))
            st.markdown(f"**Patch available:** {'✅ Yes' if analysis.get('patch_available') else '❌ Not yet'}")
            st.markdown(f"**Recommended action:** {analysis.get('recommended_action','')}")
            st.caption(f"Data sources: {', '.join(analysis.get('data_sources', []))}")

            under_the_hood(
                code_snippet="""\
# The tool-calling loop — runs until no more tool_calls
while True:
    response = await client.chat.completions.create(
        messages=messages, tools=TOOLS, tool_choice="auto"
    )
    if response.choices[0].message.tool_calls:
        for tc in response.choices[0].message.tool_calls:
            result = await execute_tool(tc)   # real API call
            messages.append(tool_result(tc.id, result))
        continue   # give model the results, loop again
    break          # model finished, no more tool calls""",
                explanation="The model emits tool_call objects instead of text when it needs data. "
                            "We execute the call and append the result to the conversation. "
                            "The model reads the result and decides whether to call another tool "
                            "or produce a final response. This is the ReAct loop.",
            )
            try_next_cve("l4")

# ─── L4b — MULTIMODAL ─────────────────────────────────────────────────────────

def render_l4b() -> None:
    st.title("L4b — Multimodal Inputs")
    lesson_objective("L4b", "See how image/PDF evidence becomes structured fields with quotes.", "you can identify extracted values and the exact grounding snippets")

    concept_box(
        title="The agent reads images and PDFs — not just text",
        what="Point the agent at an advisory screenshot (image) or a patch bulletin (PDF). "
             "It extracts the CVE id, affected product, and severity claims, and quotes the "
             "exact lines it relied on so the extraction stays auditable.",
        why="Real security intel arrives as screenshots pasted into tickets and PDF bulletins — "
            "not clean API responses. A vision model can read these directly instead of asking "
            "a human to re-type them.",
        key_idea='content becomes a LIST of parts: [{"type":"text",...}, {"type":"image_url",...}]',
    )
    learner_flow(
        "L4b",
        "Read image and extract / Parse PDF and extract",
        "grounding quotes and extracted identity fields",
        "L5 for memory over repeated incidents",
    )
    learner_coach(
        "Start with a clean advisory screenshot/PDF that clearly contains CVE and severity text.",
        "Check grounding quotes; weak quotes usually mean weak extraction confidence.",
        "Assuming extraction quality is high when source text is sparse or blurry.",
    )

    tab_img, tab_pdf = st.tabs(["🖼️  Image", "📄  PDF"])

    def _render_extract(extract: dict, data: dict) -> None:
        st.success("✅ Extraction complete")
        cost_line(data)

        col1, col2, col3 = st.columns(3)
        col1.metric("CVE ID", extract.get("cve_id") or "—")
        col2.metric("Affected Product", extract.get("affected_product") or "—")
        col3.metric("Claimed Severity", extract.get("claimed_severity") or "—")

        fields = extract.get("extracted_fields", [])
        if fields:
            st.markdown("### Extracted Fields")
            for f in fields:
                st.markdown(f"**{f.get('name','?')}:** {f.get('value','')}")

        quotes = extract.get("grounding_quotes", [])
        if quotes:
            st.markdown("### Grounding Quotes")
            st.caption("The exact source lines the model relied on — extraction is traceable, not hallucinated.")
            for q in quotes:
                st.markdown(f"> {q}")

        with st.expander("Raw extract JSON", expanded=False):
            st.json(extract)

    with tab_img:
        st.caption("Provide a public image URL or a base64 data URI of an advisory screenshot.")
        image_url = st.text_input(
            "Image URL or data URI",
            key="l4b_image_url",
            placeholder="https://example.com/advisory.png",
        )
        if st.button("Read image and extract", type="primary", key="l4b_img_run"):
            if not image_url.strip():
                st.warning("Enter an image URL or data URI first.")
            else:
                with st.spinner("Vision model reading the image…"):
                    data = api("POST", "/l4b/image", json={"image_url": image_url.strip()})
                if data:
                    _render_extract(data.get("extract", {}), data)

    with tab_pdf:
        st.caption("Upload a patch bulletin PDF. Text is extracted locally (pypdf), then sent to the model.")
        pdf_file = st.file_uploader("Advisory PDF", type=["pdf"], key="l4b_pdf_file")
        if st.button("Parse PDF and extract", type="primary", key="l4b_pdf_run"):
            if pdf_file is None:
                st.warning("Upload a PDF first.")
            else:
                content_b64 = base64.b64encode(pdf_file.getvalue()).decode("ascii")
                with st.spinner("Extracting text and analysing…"):
                    data = api(
                        "POST",
                        "/l4b/pdf",
                        json={"content_base64": content_b64, "filename": pdf_file.name},
                    )
                if data:
                    _render_extract(data.get("extract", {}), data)

    under_the_hood(
        code_snippet='''\
# A multimodal message — content is a LIST of typed parts
messages = [{
    "role": "user",
    "content": [
        {"type": "text",      "text": "Extract the advisory fields."},
        {"type": "image_url", "image_url": {"url": image_url}},
    ],
}]
# PDFs are read to text first, then grounded on:
text = extract_pdf_text(path)   # pypdf
messages = [{"role": "user", "content": f"Bulletin text:\\n{text}"}]''',
        explanation="Vision models accept an image_url part (a public URL or a base64 data URI). "
                    "PDFs aren't read natively here — we extract the text with pypdf first, then the "
                    "model grounds its answer on that text and quotes the lines it used.",
    )
    try_next_cve("l4b")

# ─── L5 ───────────────────────────────────────────────────────────────────────

def render_l5() -> None:
    st.title("L5 — Memory & Feedback Loops")
    lesson_objective("L5", "Observe how historical context changes current recommendations.", "you can explain notable change and memory_context_used behavior")

    concept_box(
        title="Agent remembers past analyses and learns from what happened next",
        what="Before each analysis, the agent retrieves past analyses for this CVE from PostgreSQL "
             "and injects them into its system prompt. After analysis, it stores the new result. "
             "You can record what you actually did — patched, dismissed, etc.",
        why="Without memory, the agent gives the same advice on day 60 as day 1. "
            "With memory, it knows you dismissed this before and EPSS has since tripled.",
        key_idea="history = await get_history(db, cve_id)  →  inject as context  →  analyse  →  save",
    )
    learner_flow(
        "L5",
        "Analyse with memory",
        "history count, notable change, and context-window budget",
        "L6 to automate repeated monitoring",
    )
    learner_coach(
        "Run once, record feedback, then run again on the same CVE.",
        "Look for changed recommendation and context-budget behavior.",
        "Testing memory with only one run and expecting visible change.",
    )

    cve_id = cve_input("l5_cve")
    tabs   = st.tabs(["Run Analysis", "Record Feedback", "View History"])

    with tabs[0]:
        if st.button("Analyse with memory", type="primary", key="l5_run"):
            with st.spinner("Checking memory, fetching live data, analysing…"):
                data = api("POST", "/l5/analyse", json={"cve_id": cve_id})

            if data:
                a = data.get("analysis", {})

                history_count = data.get("prior_history_count", 0)
                if history_count == 0:
                    st.info("🆕 First analysis for this CVE — no prior memory found.")
                else:
                    st.success(f"📚 Found {history_count} prior analysis/analyses in memory.")

                st.success("✅ Done")
                cost_line(data)
                result_hint("Interpretation", "If memory_context_used is Yes and notable_change is meaningful, your historical context is influencing decisions correctly.")

                col1, col2, col3, col4 = st.columns(4)
                col1.metric("CVSS", a.get("cvss_score", "?"))
                col2.metric("EPSS", f"{a.get('epss_score',0):.4f}")
                col3.metric("Times analysed", a.get("times_analysed", 1))
                col4.markdown(
                    f"**Memory used**<br>{'✅ Yes' if a.get('memory_context_used') else '❌ No'}",
                    unsafe_allow_html=True,
                )

                if a.get("memory_context_used"):
                    st.markdown(
                        f'<div style="background:#1E3A5F;border-left:4px solid #3B82F6;'
                        f'padding:12px;border-radius:4px">'
                        f'<b>Notable change since last analysis:</b><br>'
                        f'{a.get("notable_change","")}</div>',
                        unsafe_allow_html=True,
                    )

                st.markdown(f"**Recommendation:** {a.get('recommended_action','')}")
                st.caption(f"First seen: {a.get('first_seen','?')} · Patch: {'Available' if a.get('patch_available') else 'Not available'}")

                budget = data.get("context_budget")
                if budget:
                    st.markdown("#### Context-Window Budget (F5)")
                    used = budget.get("used_tokens", 0)
                    cap = budget.get("budget_tokens", 1) or 1
                    st.progress(min(used / cap, 1.0))
                    b1, b2, b3 = st.columns(3)
                    b1.metric("Tokens used", f"{used} / {cap}")
                    b2.metric("Verbatim entries", budget.get("entries_verbatim", 0))
                    b3.metric("Summarized entries", budget.get("entries_summarized", 0))
                    if budget.get("was_summarized"):
                        st.caption("📝 Older history was summarized to fit the token budget.")
                    if budget.get("was_truncated"):
                        st.caption("✂️ History was truncated — oldest entries dropped to respect the budget.")
                    if not budget.get("was_summarized") and not budget.get("was_truncated"):
                        st.caption("All history fit verbatim within the budget.")

        st.markdown("Record what your team actually did after the analysis.")
        st.caption("This feedback is read on the next analysis of this CVE.")

        status = st.selectbox(
            "Outcome",
            ["patched", "dismissed", "in_progress", "still_vulnerable", "monitoring"],
            key="l5_status",
        )
        notes = st.text_area("Notes (optional)", key="l5_notes",
                             placeholder="e.g. Upgraded to Log4j 2.17.1 on all services")

        if st.button("Save feedback", key="l5_feedback"):
            result = api("POST", "/l5/feedback", json={
                "cve_id": cve_id, "status": status, "notes": notes
            })
            if result and result.get("recorded"):
                st.success(result["message"])

    with tabs[2]:
        if st.button("Load history", key="l5_history"):
            data = api("GET", f"/l5/history/{cve_id}")
            if data:
                history = data.get("history", [])
                if not history:
                    st.info("No history found for this CVE yet.")
                else:
                    st.markdown(f"**{len(history)} analysis/analyses found:**")
                    for entry in history:
                        ts     = entry.get("created_at", "?")[:10]
                        result = entry.get("result", {})
                        fb     = entry.get("feedback_status")
                        with st.expander(
                            f"{ts}  CVSS {result.get('cvss_score','?')}  EPSS {result.get('epss_score',0):.3f}"
                            + (f"  ✅ {fb}" if fb else "")
                        ):
                            st.json(result)

    under_the_hood(
        code_snippet="""\
# 1. Recall
history  = await get_history(conn, cve_id)
context  = build_memory_context(history)   # format for the prompt

# 2. Inject into system prompt
messages = [{"role":"system", "content": SYSTEM + context}, ...]

# 3. Analyse (tool loop from L4)
analysis, tool_log = await run_memory_aware_loop(cve_id, context)

# 4. Remember
await save_analysis(conn, cve_id, analysis.model_dump(), tool_log)""",
        explanation="Memory injection is simple: format the history as text, prepend it to the "
                    "system prompt. The model reads it before calling any tools. This is "
                    "'in-context learning' — no fine-tuning, no embeddings, just well-formatted text.",
    )
    try_next_cve("l5")

# ─── L6 ───────────────────────────────────────────────────────────────────────

def render_l6() -> None:
    st.title("L6 — Autonomous Monitoring")
    lesson_objective("L6", "Operate an autonomous loop safely with watchlist, alerts, and control.", "you can add, scan, inspect alerts, and stop the monitor confidently")

    concept_box(
        title="The agent acts without being asked",
        what="You add CVEs to a watchlist. A background loop scans them on a schedule, "
             "detects changes (EPSS spikes, new patches), and generates alerts. "
             "You check alerts when you want — they're already there.",
        why="Without autonomy: you ask → agent answers. With autonomy: agent monitors → "
            "agent alerts → you respond to what matters. The difference is who initiates.",
        key_idea="asyncio.create_task(_monitor_loop())  — runs forever alongside the API",
    )
    learner_flow(
        "L6",
        "Add CVE to watchlist, then Run manual scan now",
        "new alerts, acknowledgement flow, and monitor state",
        "R1-R4 to harden reliability and safety",
    )
    learner_coach(
        "Add at least one CVE before running a manual scan.",
        "Use monitor status and alerts together; they answer different questions.",
        "Confusing 'monitor running' with 'new alerts generated'.",
    )

    tabs = st.tabs(["Watchlist", "Alerts", "Monitor Control"])

    with tabs[0]:
        col_add, col_list = st.columns([1, 2])

        with col_add:
            st.markdown("**Add to watchlist**")
            new_cve = st.text_input("CVE ID", value="CVE-2021-44228", key="l6_add_cve")
            if st.button("➕ Add", key="l6_add"):
                result = api("POST", "/l6/watchlist", json={"cve_id": new_cve})
                if result:
                    status = result.get("status", "")
                    if status == "added":
                        st.success(f"Added {new_cve}")
                    else:
                        st.info(f"{new_cve} was already being watched")

        with col_list:
            st.markdown("**Current watchlist**")
            if st.button("🔄 Refresh", key="l6_refresh_wl"):
                st.session_state["l6_watchlist"] = api("GET", "/l6/watchlist")

            wl_data = st.session_state.get("l6_watchlist") or api("GET", "/l6/watchlist")
            if wl_data:
                wl = wl_data.get("watchlist", [])
                if not wl:
                    st.caption("Watchlist is empty.")
                else:
                    for entry in wl:
                        c1, c2, c3 = st.columns([2, 2, 1])
                        c1.markdown(f"`{entry['cve_id']}`")
                        c2.caption(f"Last scanned: {entry.get('last_scanned','Never')[:16] if entry.get('last_scanned') else 'Never'}")
                        if c3.button("Remove", key=f"rm_{entry['cve_id']}"):
                            api("DELETE", f"/l6/watchlist/{entry['cve_id']}")
                            st.rerun()

        st.divider()
        if st.button("🔍 Run manual scan now", type="primary", key="l6_scan"):
            with st.spinner("Scanning all watched CVEs in parallel…"):
                result = api("POST", "/l6/scan")
            if result:
                st.success(
                    f"Scan complete: **{result.get('scanned',0)}** CVEs scanned, "
                    f"**{result.get('alerts_created',0)}** alerts generated."
                )

    with tabs[1]:
        filter_unacked = st.checkbox("Show unacknowledged only", value=True, key="l6_filter")
        if st.button("🔄 Load alerts", key="l6_load_alerts"):
            st.session_state["l6_alerts"] = api(
                "GET", f"/l6/alerts?unacknowledged_only={'true' if filter_unacked else 'false'}"
            )

        alerts_data = st.session_state.get("l6_alerts") or api(
            "GET", f"/l6/alerts?unacknowledged_only={'true' if filter_unacked else 'false'}"
        )

        if alerts_data:
            alerts = alerts_data.get("alerts", [])
            if not alerts:
                st.success("No alerts" + (" awaiting review" if filter_unacked else "") + ".")
            else:
                st.markdown(f"**{len(alerts)} alert(s):**")
                for alert in alerts:
                    sev    = alert.get("severity", "Informational")
                    colour = severity_colour(sev)
                    acked  = alert.get("acknowledged", False)

                    with st.expander(
                        f"#{alert['id']} [{sev}] {alert['cve_id']} — {alert['alert_type']}"
                        + ("  ✅" if acked else "  ⚠️ NEEDS REVIEW"),
                        expanded=not acked,
                    ):
                        st.markdown(
                            f'<div style="border-left:3px solid {colour};padding:8px 12px">'
                            f'{alert.get("summary","")}</div>',
                            unsafe_allow_html=True,
                        )
                        col1, col2 = st.columns(2)
                        col1.metric("EPSS", f"{alert.get('epss_now',0):.4f}")
                        col2.metric("CVSS", alert.get("cvss_now", "?"))
                        st.markdown(f"**Recommended action:** {alert.get('recommended_action','')}")
                        st.caption(f"Generated: {alert.get('created_at','?')[:16]}")

                        if not acked:
                            if st.button(f"✅ Acknowledge #{alert['id']}", key=f"ack_{alert['id']}"):
                                result = api(
                                    "POST",
                                    f"/l6/alerts/{alert['id']}/acknowledge",
                                    json={"acknowledged_by": "ui-user"},
                                )
                                if result:
                                    st.success("Acknowledged")
                                    st.rerun()

    with tabs[2]:
        status_data = api("GET", "/l6/monitor/status")

        if status_data:
            running = status_data.get("running", False)
            col1, col2, col3, col4 = st.columns(4)
            col1.markdown(
                f"**Status**<br>"
                f"{'🟢 Running' if running else '🔴 Stopped'}",
                unsafe_allow_html=True,
            )
            col2.metric("Scan interval", f"{status_data.get('scan_interval_seconds',3600)}s")
            col3.metric("Watchlist", f"{status_data.get('watchlist_size',0)} CVEs")
            col4.metric("Unacked alerts", status_data.get("unacknowledged_alert_count", 0))

            if status_data.get("last_scan"):
                st.caption(f"Last scan: {status_data['last_scan'][:19]} UTC")

            st.divider()
            col_start, col_stop = st.columns(2)
            with col_start:
                if st.button("▶️ Start autonomous monitor", type="primary",
                             disabled=running, key="l6_start"):
                    result = api("POST", "/l6/monitor/start")
                    if result:
                        st.success(result.get("message", "Started"))
                        st.rerun()

            with col_stop:
                if st.button("🛑 Kill switch — stop monitor", type="secondary",
                             disabled=not running, key="l6_stop"):
                    result = api("POST", "/l6/monitor/stop")
                    if result:
                        st.warning(result.get("message", "Stopped"))
                        st.rerun()

        st.divider()
        under_the_hood(
            code_snippet="""\
async def _monitor_loop(db_url):
    while not _stop_event.is_set():
        await scan_all_once(db_url)   # scan every CVE in watchlist
        try:
            # Sleep until interval elapses OR stop is requested
            await asyncio.wait_for(
                _stop_event.wait(),
                timeout=SCAN_INTERVAL_SECONDS
            )
        except asyncio.TimeoutError:
            pass  # time to scan again

# Kill switch: wakes the sleeping loop immediately
async def stop_monitor():
    _stop_event.set()
    _monitor_task.cancel()""",
            explanation="asyncio.wait_for(_stop_event.wait()) is the key pattern. "
                        "asyncio.sleep() would make the kill switch wait out the full interval. "
                        "The event-based approach means stop() takes effect in milliseconds, "
                        "not at the end of the next hour-long sleep.",
        )


# ─── F8 ───────────────────────────────────────────────────────────────────────

def render_f8() -> None:
    st.title("F8 — Tool Discovery & MCP")

    concept_box(
        title="Tools described as data, so any client can find and use them",
        what="L4's tools can come from inline definitions or from an MCP-style tool server. Either way a tool is "
             "a name, a description and a JSON schema that the model reads to decide when to call it.",
        why="Describing tools as data decouples the agent from the code behind them. Add or change a tool "
            "without rewriting the agent, and let different clients share one set of tools.",
        key_idea="tool = name + description + input schema; the client discovers, then calls",
    )
    st.info(
        "Honest note: in Vigil the MCP client runs **in the same process** as the API and calls the tool functions "
        "directly. It teaches the message shapes and the loop, not a real separate MCP server process. "
        "The tool loop calls the public NVD and EPSS services; it uses no paid model."
    )

    tabs = st.tabs(["Discover tools", "Run a tool loop"])

    with tabs[0]:
        source = st.radio("Tool source", ["inline", "mcp"], horizontal=True, key="f8_source")
        if st.button("Discover", type="primary", key="f8_discover"):
            tools = api("GET", f"/l4/tools?source={source}")
            if tools:
                st.dataframe(
                    [{"name": t["name"], "source": t["source"], "description": t["description"]} for t in tools],
                    use_container_width=True,
                )
                for t in tools:
                    with st.expander(f"Input schema: {t['name']}"):
                        st.json(t["input_schema"])

    with tabs[1]:
        cve_id = cve_input("vigil_cve")
        if st.button("Run tool loop", type="primary", key="f8_loop"):
            with st.spinner("Calling NVD and EPSS through the tool loop…"):
                data = api("POST", "/mcp/tool-loop", json={"cve_id": cve_id})
            if data:
                st.success(f"{data.get('tool_calls', 0)} tool calls · stop reason: {data.get('stop_reason', '?')}")
                for step in data.get("transcript", []):
                    with st.expander(f"Tool: {step.get('tool', '?')}", expanded=False):
                        st.markdown("**Arguments**")
                        st.json(step.get("arguments", {}))
                        st.markdown("**Result**")
                        st.json(step.get("result", {}))
