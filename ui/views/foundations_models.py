"""Foundations pages F21-F22 (fine-tune advisor, Claude model selection)."""

import streamlit as st

from common import (
    api,
    concept_box,
    learner_coach,
    learner_flow,
    lesson_objective,
    result_hint,
)


# ─── F21 ──────────────────────────────────────────────────────────────────────

def render_f21() -> None:
    st.title("F21 — Fine-tune Advisor & Build-vs-Tune")
    lesson_objective("F21", "Decide between prompting, RAG, and fine-tuning from task traits.", "you can justify an adaptation strategy and check dataset readiness")

    concept_box(
        title="Fine-tuning is a decision, not a default",
        what="Get an approach recommendation from task traits, and validate a fine-tuning dataset.",
        why="Choosing prompt/RAG/LoRA correctly saves cost and avoids premature training.",
        key_idea="task traits -> ranked approaches; dataset -> readiness check",
    )
    learner_flow(
        "F21",
        "Get a recommendation and validate data",
        "ranked approaches, reasons, and dataset readiness",
        "F14 to version prompts or F12 to measure RAG quality first",
    )
    learner_coach(
        "Change one trait at a time to see how the recommendation shifts.",
        "Read the reasons, not just the top approach.",
        "Fine-tuning for fresh-knowledge tasks that RAG solves more cheaply.",
    )

    tab_advisor, tab_data = st.tabs(["Approach Advisor", "Dataset Validator"])

    with tab_advisor:
        c1, c2 = st.columns(2)
        data_volume = c1.number_input("Labeled examples", min_value=0, value=1500, step=100, key="f21_vol")
        stability = c2.selectbox("Task stability", ["stable", "unstable"], key="f21_stab")
        c3, c4 = st.columns(2)
        fresh = c3.checkbox("Needs fresh knowledge", value=False, key="f21_fresh")
        strict = c4.checkbox("Strict output format", value=True, key="f21_strict")
        c5, c6 = st.columns(2)
        latency = c5.checkbox("Latency sensitive", value=False, key="f21_lat")
        domain = c6.selectbox("Domain shift", ["low", "high"], key="f21_domain")

        if st.button("Recommend approach", type="primary", key="f21_run"):
            data = api(
                "POST",
                "/foundations/adaptation/recommend",
                json={
                    "task_stability": stability,
                    "data_volume": int(data_volume),
                    "needs_fresh_knowledge": fresh,
                    "strict_format": strict,
                    "latency_sensitive": latency,
                    "domain_shift": domain,
                },
            )
            if data:
                result_hint("Recommended", data.get("recommended", "?"), tone="success")
                st.dataframe(data.get("ranked", []), use_container_width=True)
                st.markdown("**Why:**")
                for r in data.get("reasons", []):
                    st.markdown(f"- {r}")
                st.info(data.get("guidance", ""))

    with tab_data:
        st.caption("Paste JSONL-style records (one JSON object per line) with a messages array.")
        default_blob = (
            '{"messages":[{"role":"user","content":"Summarize CVE-2021-44228"},{"role":"assistant","content":"Log4Shell RCE"}]}\n'
            '{"messages":[{"role":"user","content":"Summarize CVE-2021-44228"},{"role":"assistant","content":"Log4Shell RCE"}]}'
        )
        blob = st.text_area("Dataset (JSONL)", value=default_blob, key="f21_data", height=160)

        if st.button("Validate dataset", type="primary", key="f21_validate"):
            records = []
            parse_error = None
            for line in blob.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    import json as _json
                    records.append(_json.loads(line))
                except Exception as e:
                    parse_error = str(e)
                    break

            if parse_error:
                st.error(f"Parse error: {parse_error}")
            else:
                data = api("POST", "/foundations/finetune/validate", json={"records": records})
                if data:
                    m1, m2, m3, m4 = st.columns(4)
                    m1.metric("Total", data.get("total", 0))
                    m2.metric("Valid", data.get("valid", 0))
                    m3.metric("Quality", data.get("quality_score", 0.0))
                    m4.metric("Ready", "Yes" if data.get("ready_to_train") else "No")
                    issues = data.get("issues", [])
                    if issues:
                        st.warning("Issues detected")
                        for issue in issues:
                            st.markdown(f"- {issue}")
                    result_hint("Interpretation", "Fix duplicates and empty completions before training; ready requires clean, sufficient data.")

# ─── F22 ──────────────────────────────────────────────────────────────────────

def render_f22() -> None:
    st.title("F22 — Claude Model Selection & Context Engineering")
    lesson_objective("F22", "Pick the right Claude tier (Haiku/Sonnet/Opus) from constraints.", "you can justify a model tier and an escalation path")

    concept_box(
        title="Model selection is an architecture decision",
        what="Recommend a Claude tier from complexity, latency, cost, volume, and stakes.",
        why="Right-sizing the model is a core Claude-architect skill: start cheap, escalate on evidence.",
        key_idea="constraints -> ranked tiers -> start cheap, escalate when evals demand it",
    )
    learner_flow(
        "F22",
        "Recommend a model tier",
        "recommended tier, ranking, and escalation hint",
        "F21 to decide prompt vs RAG vs fine-tune for the same task",
    )
    learner_coach(
        "Toggle one constraint at a time to see tier shifts.",
        "Read the reasons and escalation hint, not just the top tier.",
        "Defaulting to the most capable tier for every task regardless of cost.",
    )

    c1, c2 = st.columns(2)
    complexity = c1.selectbox("Task complexity", ["low", "medium", "high"], index=1, key="f22_complexity")
    high_stakes = c2.checkbox("High-stakes correctness", value=False, key="f22_stakes")
    c3, c4, c5 = st.columns(3)
    latency = c3.checkbox("Latency sensitive", value=False, key="f22_lat")
    cost = c4.checkbox("Cost sensitive", value=False, key="f22_cost")
    volume = c5.checkbox("High volume", value=False, key="f22_vol")

    if st.button("Recommend model tier", type="primary", key="f22_run"):
        data = api(
            "POST",
            "/foundations/model-select",
            json={
                "task_complexity": complexity,
                "latency_sensitive": latency,
                "cost_sensitive": cost,
                "high_volume": volume,
                "high_stakes": high_stakes,
            },
        )
        if data:
            result_hint("Recommended", data.get("recommended_name", "?"), tone="success")
            st.dataframe(data.get("ranked", []), use_container_width=True)
            st.markdown("**Why:**")
            for r in data.get("reasons", []):
                st.markdown(f"- {r}")
            st.info(data.get("escalation_hint", ""))

    st.divider()
    st.caption("Claude bridge: map OpenAI-style messages to the Claude Messages API shape (system param + content blocks).")
    if st.button("Show Claude message mapping", key="f22_map"):
        data = api(
            "POST",
            "/claude/map-messages",
            json={
                "messages": [
                    {"role": "system", "content": "You are a grounded CVE analyst."},
                    {"role": "user", "content": "Summarize CVE-2021-44228."},
                ]
            },
        )
        if data:
            st.json(data)
