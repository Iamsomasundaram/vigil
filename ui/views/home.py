"""Home page."""

import streamlit as st


# ─── HOME ─────────────────────────────────────────────────────────────────────

def render_home() -> None:
    st.title("🛡️ VIGIL — GenAI Learning Lab")
    st.markdown(
        "A hands-on tour of **agentic AI**, built around real vulnerability "
        "management. Every page teaches **one** concept, with a live demo you can run."
    )

    with st.container(border=True):
        st.markdown("#### 🚀 How to use this lab")
        s1, s2, s3 = st.columns(3)
        s1.markdown("**1. Pick a track**  \nUse the sidebar: start with *Learning Levels*, then explore *Reliability*, *Extensions*, and *Architectures*.")
        s2.markdown("**2. Set a CVE once**  \nType a CVE on any page — it's remembered everywhere, so you never re-type it.")
        s3.markdown("**3. Run & read**  \nHit the primary button, then open *Under the hood* to see the exact code that ran.")

        st.caption("Suggested path:  L0 → L1 → L2 → L3 → L4 → L5 → L6,  then R1–R4,  then E1–E4,  then A1–A4.")
        qs1, qs2 = st.columns([3, 1])
        quick_cve = qs1.text_input(
            "Quick-set the working CVE",
            value=st.session_state.get("vigil_cve", "CVE-2021-44228"),
            key="home_quick_cve",
            label_visibility="collapsed",
        )
        if qs2.button("Use this CVE", type="primary", use_container_width=True, key="home_set_cve"):
            st.session_state["vigil_cve"] = quick_cve.strip() or "CVE-2021-44228"
            st.success(f"Working CVE set to {st.session_state['vigil_cve']}")

    st.divider()
    st.markdown("### Start Here in 20 Minutes")
    st.markdown(
        "1. Run **L0** once to see the raw model baseline.  "
        "2. Run **L1** and compare structure/clarity vs L0.  "
        "3. Run **L4** to see grounded tool-based analysis.  "
        "4. Run **L5** twice to observe memory effects."
    )

    st.divider()

    cols = st.columns(3)
    level_cards = [
        ("L0", "Single LLM Call",       "One prompt, one response. The atomic unit of all AI.",          "#6366F1"),
        ("L1", "Prompt Chain",           "3 sequential calls — each output feeds the next.",              "#8B5CF6"),
        ("L2", "Parallel Fan-out",       "4 agents run at once. Faster than sequential, richer output.",  "#A855F7"),
        ("L3", "Conditional Routing",    "The LLM decides which pipeline to run.",                        "#EC4899"),
        ("L4", "Tool Use",               "Agent calls real NVD + EPSS APIs. Grounded, not memorised.",    "#F59E0B"),
        ("L4b", "Multimodal",            "Reads advisory images and PDF bulletins, not just text.",        "#F97316"),
        ("L5", "Memory & Feedback",      "Remembers past analyses. Learns from what happened.",           "#10B981"),
        ("L6", "Autonomous Monitor",     "Acts without being asked. Watchlist, alerts, kill switch.",     "#EF4444"),
    ]

    for i, (level, title, desc, colour) in enumerate(level_cards):
        with cols[i % 3]:
            st.markdown(
                f"""
                <div style="background:#1E1E2E;border-top:3px solid {colour};
                            padding:14px;border-radius:6px;margin-bottom:12px;height:130px">
                  <div style="color:{colour};font-weight:bold">{level}</div>
                  <div style="color:#E2E8F0;font-size:1em;font-weight:600">{title}</div>
                  <div style="color:#94A3B8;font-size:0.85em;margin-top:4px">{desc}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.markdown("**Axis Extensions (E1-E4):**")
    ext_cols = st.columns(4)
    extension_cards = [
        ("E1", "Semantic Memory", "Retrieve similar past CVEs by vector similarity.", "#0EA5E9"),
        ("E2", "Human-in-the-Loop", "Pause risky actions for explicit approval or reject.", "#F97316"),
        ("E3", "Agent Communication", "Compare handoff, debate, and blackboard coordination.", "#22C55E"),
        ("E4", "Inference Layer", "Policy-based model fallback and streaming responses.", "#EAB308"),
    ]

    for i, (ext, title, desc, colour) in enumerate(extension_cards):
        with ext_cols[i]:
            st.markdown(
                f"""
                <div style="background:#161B2A;border:1px solid #2B3550;border-left:3px solid {colour};
                            padding:12px;border-radius:6px;margin-bottom:10px;height:120px">
                  <div style="color:{colour};font-weight:bold">{ext}</div>
                  <div style="color:#E2E8F0;font-size:0.95em;font-weight:600">{title}</div>
                  <div style="color:#9CA3AF;font-size:0.82em;margin-top:4px">{desc}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.divider()
    st.markdown("**Recommended CVEs to try:**")
    st.table({
        "CVE": ["CVE-2021-44228", "CVE-2023-44487", "CVE-2014-0160"],
        "Name": ["Log4Shell", "HTTP/2 Rapid Reset", "Heartbleed"],
        "Why interesting": [
            "CVSS 10.0, EPSS ~94% — consistently routes to critical track",
            "High-profile DoS — routes to standard patch",
            "Classic, well-known — tests memory across runs",
        ],
    })
