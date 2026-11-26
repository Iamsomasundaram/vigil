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

from common import API_BASE, DEMO_SHOP_URL, DOCS_URL, api, guide_url  # noqa: E402
from nav import GUIDE_LINKS, GUIDE_PAGES, NAV_GROUPS  # noqa: E402
from registry import PAGES  # noqa: E402

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

    group = st.selectbox(
        "Section",
        list(NAV_GROUPS.keys()),
        key="nav_group",
        help="The sections follow the learning guide. New here: Start, then Levels L0-L6.",
    )
    items = NAV_GROUPS[group]
    # No key on this radio: when the group changes its options change, so it
    # naturally resets to the first page of the newly selected track.
    selected = st.radio("Page", list(items.keys()), label_visibility="collapsed")
    page = items[selected]

    st.divider()
    st.caption("Suggested sequence")
    st.caption("Start -> Levels L0-L6 -> Architectures A1-A4 -> Reliability R1-R9 -> Foundations -> Extensions")

    st.divider()
    st.caption("Active CVE")
    st.markdown(f"`{st.session_state.get('vigil_cve', 'CVE-2021-44228')}`")
    st.caption("Set it on any page — it follows you everywhere.")

    st.divider()
    st.caption("API docs → [Swagger UI](%s/docs)  ·  [ReDoc](%s/redoc)" % (API_BASE, API_BASE))

    with st.expander("📚 Learning guide", expanded=False):
        for label, slug in GUIDE_LINKS:
            st.markdown(f"- [{label}]({guide_url(slug)})")
        st.caption("The guide is a separate site. Under Docker Compose it runs at " + DOCS_URL + ".")
    st.caption("🛍️ [Demo shop](%s) (target for P1)" % DEMO_SHOP_URL)


# ─── PAGE DISPATCH ────────────────────────────────────────────────────────────
# Each page lives in ui/views/<module>.py as a render_<page>() function; ui/registry.py maps
# page keys to them and ui/nav.py maps the same keys to the sidebar and to guide pages.

slug = GUIDE_PAGES.get(page)
if slug:
    st.caption(f"📚 Read the guide page for this topic: [{slug}]({guide_url(slug)})")

renderer = PAGES.get(page)
if renderer is not None:
    renderer()
