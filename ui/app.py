"""
VIGIL — Learning Lab UI
========================
A Streamlit interface for exploring all 6 levels of agentic AI.

Each level has:
  - A concept panel explaining WHAT and WHY
  - An interactive form to run the level against any CVE
  - A results display that visualises the output
  - An "Under the hood" section showing what the code does

Run:
  streamlit run ui/app.py

The app talks to the Vigil FastAPI service.
Set VIGIL_API_URL if the API is not on localhost:8000.
"""

import sys
from pathlib import Path

import streamlit as st

# `streamlit run ui/app.py` puts this folder on sys.path; make it explicit so the sibling
# modules import the same way under any launcher (and inside the Docker image).
_HERE = str(Path(__file__).resolve().parent)
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from common import API_BASE, api  # noqa: E402
from views import (  # noqa: E402
    home,
    reference,
    checklist,
    levels_core,
    levels_tools,
    reliability,
    extensions,
    foundations,
    foundations_models,
    governance,
    themes,
    architectures,
)

# ─── CONFIG ───────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="VIGIL — GenAI Learning Lab",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
        """
        <style>
            .vigil-kicker {
                color: #93C5FD;
                font-weight: 700;
                letter-spacing: 0.03em;
                text-transform: uppercase;
                font-size: 0.77rem;
                margin-bottom: 0.25rem;
            }
            .vigil-step {
                color: #E2E8F0;
                font-size: 0.92em;
                margin: 2px 0;
            }
        </style>
        """,
        unsafe_allow_html=True,
)

# The CVE the user is working with, shared across every page so it never
# has to be re-typed when moving between levels.
st.session_state.setdefault("vigil_cve", "CVE-2021-44228")

# ─── SIDEBAR ──────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("## 🛡️ VIGIL")
    st.markdown("**Autonomous CVE Intelligence**  \nGenAI Learning Lab")
    st.divider()

    # Check API connectivity
    health = api("GET", "/health")
    if health:
        st.success(f"API connected  `{API_BASE}`")
    else:
        st.error("API not reachable")

    st.divider()

    NAV_GROUPS = {
        "1) Start": {
            "🏠 Home":                  "home",
            "📖 Glossary":              "glossary",
            "📋 Prod Readiness":        "checklist",
        },
        "2) Core Levels": {
            "L0 — Single LLM Call":     "l0",
            "L1 — Prompt Chain":        "l1",
            "L2 — Parallel Fan-out":    "l2",
            "L3 — Conditional Routing": "l3",
            "L4 — Tool Use":            "l4",
            "L4b — Multimodal":         "l4b",
            "L5 — Memory & Feedback":   "l5",
            "L6 — Autonomous Monitor":  "l6",
        },
        "3) Reliability": {
            "R1 — Guardrails":          "r1",
            "R2 — Evaluation":          "r2",
            "R3 — Observability":       "r3",
            "R4 — Resilience":          "r4",
        },
        "4) Foundations": {
            "F4 — Tokenization":        "f4",
            "F6 — Prompt Techniques":   "f6",
            "F11 — Retrieval Quality":  "f11",
            "F12 — Retrieval Metrics":  "f12",
            "F13 — Factuality":         "f13",
            "F14 — Prompt Lifecycle":   "f14",
            "F15 — Privacy":            "f15",
            "F16 — Hybrid Retrieval":   "f16",
            "F21 — Fine-tune Advisor":  "f21",
            "F22 — Claude Model Select": "f22",
        },
        "5) Extensions": {
            "E1 — Semantic Memory":     "e1",
            "E2 — Human-in-the-Loop":   "e2",
            "E3 — Agent Communication": "e3",
            "E4 — Inference Layer":     "e4",
        },
        "6) Architectures": {
            "A1 — ReAct":               "a1",
            "A2 — Plan-and-Execute":    "a2",
            "A3 — Reflection":          "a3",
            "A4 — Multi-Agent":         "a4",
        },
        "7) Themes": {
            "T1 — Incident Response Ops": "t1_incident",
        },
        "8) Governance & Ops": {
            "F17 — Drift Monitoring":   "f17",
            "F18 — Action Governance":  "f18",
            "F19 — Supply Chain":       "f19",
            "F20 — Release Safety":     "f20",
            "F23 — Responsible AI":     "f23",
            "F24 — Semantic Cache":     "f24",
        },
    }

    group = st.selectbox(
        "Section",
        list(NAV_GROUPS.keys()),
        key="nav_group",
        help="If new: Start -> Core Levels (L0-L6) -> Reliability -> Extensions/Architectures.",
    )
    items = NAV_GROUPS[group]
    # No key on this radio: when the group changes its options change, so it
    # naturally resets to the first page of the newly selected track.
    selected = st.radio("Page", list(items.keys()), label_visibility="collapsed")
    page = items[selected]

    st.divider()
    st.caption("Suggested sequence")
    st.caption("Start -> L0-L6 -> R1-R4 -> F4/F6/F11/F12/F13/F14/F15 -> E1-E4 -> A1-A4")

    st.divider()
    st.caption("Active CVE")
    st.markdown(f"`{st.session_state.get('vigil_cve', 'CVE-2021-44228')}`")
    st.caption("Set it on any page — it follows you everywhere.")

    st.divider()
    st.caption("Docs → [Swagger UI](%s/docs)  ·  [ReDoc](%s/redoc)" % (API_BASE, API_BASE))


# ─── PAGE DISPATCH ────────────────────────────────────────────────────────────
# Each page lives in ui/views/<module>.py as a render_<page>() function.

PAGES = {
    "home": home.render_home,
    "glossary": reference.render_glossary,
    "checklist": checklist.render_checklist,
    "l0": levels_core.render_l0,
    "l1": levels_core.render_l1,
    "l2": levels_core.render_l2,
    "l3": levels_core.render_l3,
    "l4": levels_tools.render_l4,
    "l4b": levels_tools.render_l4b,
    "l5": levels_tools.render_l5,
    "l6": levels_tools.render_l6,
    "r1": reliability.render_r1,
    "r2": reliability.render_r2,
    "r3": reliability.render_r3,
    "r4": reliability.render_r4,
    "e1": extensions.render_e1,
    "e2": extensions.render_e2,
    "e3": extensions.render_e3,
    "e4": extensions.render_e4,
    "f4": foundations.render_f4,
    "f6": foundations.render_f6,
    "f11": foundations.render_f11,
    "f12": foundations.render_f12,
    "f13": foundations.render_f13,
    "f14": foundations.render_f14,
    "f15": foundations.render_f15,
    "f16": foundations.render_f16,
    "f21": foundations_models.render_f21,
    "f22": foundations_models.render_f22,
    "f17": governance.render_f17,
    "f18": governance.render_f18,
    "f19": governance.render_f19,
    "f20": governance.render_f20,
    "f23": governance.render_f23,
    "f24": governance.render_f24,
    "t1_incident": themes.render_t1_incident,
    "a1": architectures.render_a1,
    "a2": architectures.render_a2,
    "a3": architectures.render_a3,
    "a4": architectures.render_a4,
}

renderer = PAGES.get(page)
if renderer is not None:
    renderer()
