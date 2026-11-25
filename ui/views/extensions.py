"""Axis extension pages E1-E4."""

import httpx
import streamlit as st

from common import (
    API_BASE,
    TIMEOUT,
    api,
    concept_box,
)


# ─── E1 ───────────────────────────────────────────────────────────────────────

def render_e1() -> None:
    st.title("E1 — Semantic Memory / RAG")

    concept_box(
        title="Recall related incidents, not just exact CVE matches",
        what="E1 retrieves semantically similar prior analyses and injects them as contextual evidence.",
        why="Teams often solved related incidents before. Semantic recall helps transfer those lessons.",
        key_idea="query_cve -> top-k similar matches -> labeled context in analysis prompt",
    )

    c1, c2, c3 = st.columns(3)
    cve_id = c1.text_input("CVE ID", key="vigil_cve")
    k = c2.slider("Top-k", min_value=1, max_value=10, value=5, key="e1_k")
    threshold = c3.slider("Similarity threshold", min_value=0.0, max_value=1.0, value=0.55, step=0.01, key="e1_threshold")

    if st.button("Find similar incidents", type="primary", key="e1_run"):
        data = api("GET", f"/l5/similar/{cve_id}", params={"k": k, "threshold": threshold})
        if data:
            matches = data.get("matches", [])
            st.success(f"Found {len(matches)} similar incident(s)")

            mode = data.get("embedding_mode", "local")
            dims = data.get("embedding_dims", 32)
            mc1, mc2, mc3 = st.columns(3)
            mc1.metric("Embedding backend", "OpenAI" if mode == "openai" else "Local (hash)")
            mc2.metric("Vector dimensions", dims)
            mc3.metric("Used in prompt", "Yes" if data.get("used_in_prompt") else "No")
            if mode != "openai":
                st.caption(
                    "Local hash embeddings reflect token overlap, not meaning. "
                    "Set `VIGIL_EMBED_MODE=openai` on the API to enable real semantic "
                    "embeddings (text-embedding-3-small, 1536-d)."
                )

            if not matches:
                st.info("No matches above threshold.")
            else:
                rows = []
                for m in matches:
                    rows.append(
                        {
                            "cve_id": m.get("cve_id"),
                            "similarity": m.get("similarity"),
                            "outcome": m.get("outcome") or "-",
                            "summary": m.get("summary", "")[:180],
                        }
                    )
                st.dataframe(rows, use_container_width=True)

# ─── E2 ───────────────────────────────────────────────────────────────────────

def render_e2() -> None:
    st.title("E2 — Human-in-the-Loop Approval Gates")

    concept_box(
        title="Pause, review, approve, then execute",
        what="E2 adds plan/action approval gates to A2 so high-risk runs require explicit human decisions.",
        why="Autonomous execution is powerful, but revocable control is essential in security workflows.",
        key_idea="start run -> pending gate -> decision -> resume or abort",
    )

    tabs = st.tabs(["Start Run", "Get Run", "Submit Decision"])

    with tabs[0]:
        cve_id = st.text_input("CVE ID", key="vigil_cve")
        if st.button("Start gated run", type="primary", key="e2_start"):
            data = api("POST", "/a2/start", json={"cve_id": cve_id})
            if data:
                st.success("Run created")
                st.session_state["e2_run_id"] = data.get("run_id", "")
                gate = data.get("open_gate") or {}
                st.caption(f"Run ID: {data.get('run_id', '')}")
                if gate:
                    st.info(f"Open gate: {gate.get('gate_type')} · risk={gate.get('risk')}")
                st.json(data)

    with tabs[1]:
        run_id_default = st.session_state.get("e2_run_id", "")
        run_id = st.text_input("Run ID", value=run_id_default, key="e2_get_run_id")
        if st.button("Load run", key="e2_get"):
            data = api("GET", f"/a2/runs/{run_id}")
            if data:
                run = data.get("run", {})
                st.success(f"State: {run.get('state', '?')}")
                st.json(data)

    with tabs[2]:
        run_id_default = st.session_state.get("e2_run_id", "")
        run_id = st.text_input("Run ID", value=run_id_default, key="e2_decide_run_id")
        gate_id = st.text_input("Gate ID", value="", key="e2_gate_id")
        decision = st.selectbox(
            "Decision",
            ["approve", "reject", "edit", "request_changes"],
            key="e2_decision",
        )
        actor = st.text_input("Actor", value="analyst", key="e2_actor")
        edited_payload = st.text_area("Edited payload (optional JSON string)", value="", key="e2_edited")
        rationale = st.text_area("Rationale (optional)", value="", key="e2_rationale")

        if st.button("Submit decision", type="primary", key="e2_submit"):
            payload = {
                "gate_id": gate_id,
                "decision": decision,
                "actor": actor,
                "edited_payload": edited_payload or None,
                "rationale": rationale or None,
            }
            data = api("POST", f"/a2/runs/{run_id}/decision", json=payload)
            if data:
                st.success(f"New state: {data.get('state', '?')}")
                st.json(data)

# ─── E3 ───────────────────────────────────────────────────────────────────────

def render_e3() -> None:
    st.title("E3 — Agent-to-Agent Communication")

    concept_box(
        title="Handoff, debate, and blackboard modes",
        what="E3 exposes different collaboration topologies for A4 specialists.",
        why="Multi-agent quality depends on communication pattern, not just agent count.",
        key_idea="mode selects transcript topology and consensus behavior",
    )

    c1, c2, c3 = st.columns(3)
    cve_id = c1.text_input("CVE ID", key="vigil_cve")
    mode = c2.selectbox("Mode", ["handoff", "debate", "blackboard"], key="e3_mode")
    rounds = c3.slider("Rounds", min_value=1, max_value=5, value=2, key="e3_rounds")

    if st.button("Run collaboration", type="primary", key="e3_run"):
        data = api(
            "POST",
            "/a4/collaborate",
            json={"cve_id": cve_id, "mode": mode, "rounds": rounds},
        )
        if data:
            st.success("Consensus produced")
            col1, col2, col3 = st.columns(3)
            col1.metric("Mode", data.get("mode", "?"))
            col2.metric("Rounds used", data.get("rounds_used", 0))
            col3.metric("Disagreement", "Yes" if data.get("disagreement_noted") else "No")
            st.markdown(f"**Final verdict:** {data.get('final_verdict', '')}")

            transcript = data.get("transcript", [])
            if transcript:
                rows = []
                for msg in transcript:
                    rows.append(
                        {
                            "round": msg.get("round"),
                            "sender": msg.get("sender"),
                            "recipient": msg.get("recipient"),
                            "content": msg.get("content", "")[:200],
                        }
                    )
                st.dataframe(rows, use_container_width=True)

# ─── E4 ───────────────────────────────────────────────────────────────────────

def render_e4() -> None:
    st.title("E4 — Shared Inference Layer")

    concept_box(
        title="Routing policy, fallback chain, and streaming",
        what="E4 centralizes model routing/fallback logic and provides a streaming endpoint demo.",
        why="A thin inference seam keeps cost, resilience, and behavior consistent across levels.",
        key_idea="task -> policy(primary + fallbacks) -> completion/stream",
    )

    tabs = st.tabs(["Policy", "Providers", "L1 Streaming Demo"])

    with tabs[0]:
        if st.button("Load inference policy", type="primary", key="e4_policy"):
            data = api("GET", "/inference/policy")
            if data is not None:
                st.success("Loaded policy")
                st.dataframe(data, use_container_width=True)

    with tabs[1]:
        st.caption(
            "The same AsyncOpenAI client talks to hosted OpenAI, a local Ollama model, or any "
            "OpenAI-compatible endpoint — only the base_url changes. Capability flags let the layer "
            "degrade (prompt-coerced JSON) when a local model lacks strict schema support."
        )
        if st.button("List providers", key="e4_providers"):
            providers = api("GET", "/inference/providers")
            if providers is not None:
                st.dataframe(providers, use_container_width=True)

        st.markdown("#### Compare providers on one task")
        st.caption(
            "Runs the same summary prompt against each selected provider and tabulates "
            "latency, tokens, and cost. Local providers that aren't running show a clear error."
        )
        cmp_cve = st.text_input("CVE ID", key="e4_cmp_cve", value="CVE-2021-44228")
        chosen = st.multiselect(
            "Providers",
            ["openai", "ollama", "openai_compatible"],
            default=["openai"],
            key="e4_cmp_providers",
        )
        if st.button("Run comparison", type="primary", key="e4_cmp_run"):
            if not chosen:
                st.warning("Pick at least one provider.")
            else:
                with st.spinner("Running the same prompt across providers…"):
                    data = api(
                        "POST",
                        "/inference/compare",
                        json={"cve_id": cmp_cve.strip(), "providers": chosen},
                    )
                if data:
                    st.dataframe(data.get("rows", []), use_container_width=True)

    with tabs[2]:
        cve_id = st.text_input("CVE ID", key="vigil_cve")
        if st.button("Stream summary", key="e4_stream"):
            try:
                with httpx.stream("GET", f"{API_BASE}/l1/stream", params={"cve_id": cve_id}, timeout=TIMEOUT) as r:
                    r.raise_for_status()
                    chunks: list[str] = []
                    stream_box = st.empty()
                    for chunk in r.iter_text():
                        if not chunk:
                            continue
                        chunks.append(chunk)
                        stream_box.markdown("".join(chunks))
                st.success("Streaming complete")
            except httpx.HTTPStatusError as e:
                st.error(f"API error {e.response.status_code}: {e.response.text[:300]}")
            except httpx.RequestError as e:
                st.error(f"Could not reach the API at {API_BASE}.\n\n{e}")
