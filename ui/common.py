"""Shared configuration and helpers for the Vigil learning-lab UI."""

import os

import httpx
import streamlit as st


API_BASE = os.getenv("VIGIL_API_URL", "http://localhost:8000")
# Key the UI sends as X-API-Key when the API has VIGIL_API_KEYS set (give it a run-scope key).
AUTH_HEADERS = {"x-api-key": os.environ["VIGIL_UI_API_KEY"]} if os.getenv("VIGIL_UI_API_KEY") else {}
# The UI image does not ship the vigil package, so this mirrors vigil.pricing.PRICING_NOTE.
COST_NOTE = "Estimate from indicative list prices; not a bill. Provider prices change and are not synced here."

# How long to wait for LLM-backed endpoints (they can take 20–30s)
TIMEOUT = httpx.Timeout(180.0)


# ─── SHARED HELPERS ───────────────────────────────────────────────────────────

def api(method: str, path: str, **kwargs) -> dict | None:
    """
    Call the Vigil API. Returns the parsed JSON or None on error.
    Displays a Streamlit error message if the call fails.
    """
    url = f"{API_BASE}{path}"
    try:
        headers = {**kwargs.pop("headers", {}), **AUTH_HEADERS}
        r = httpx.request(method, url, timeout=TIMEOUT, headers=headers, **kwargs)
        r.raise_for_status()
        return r.json()
    except httpx.HTTPStatusError as e:
        st.error(f"API error {e.response.status_code}: {e.response.text[:300]}")
    except httpx.RequestError as e:
        st.error(f"Could not reach the API at {API_BASE}. Is the Vigil service running?\n\n{e}")
    return None


def severity_colour(s: str) -> str:
    """Map severity label to a hex colour for display."""
    return {
        "CRITICAL": "#FF4B4B",
        "HIGH":     "#FF8C00",
        "Critical": "#FF4B4B",
        "High":     "#FF8C00",
        "Warning":  "#FF8C00",
        "Medium":   "#FFA500",
        "Low":      "#21C354",
        "Informational": "#00B4D8",
    }.get(s, "#888888")


def badge(label: str, colour: str) -> str:
    """Return an HTML badge string for st.markdown(..., unsafe_allow_html=True)."""
    return (
        f'<span style="background:{colour};color:white;padding:3px 10px;'
        f'border-radius:12px;font-weight:bold;font-size:0.85em">{label}</span>'
    )


def concept_box(title: str, what: str, why: str, key_idea: str) -> None:
    """Render the concept panel at the top of each level page."""
    st.markdown(
        f"""
        <div style="background:#1E1E2E;border-left:4px solid #7C3AED;
                    padding:16px 20px;border-radius:6px;margin-bottom:20px">
          <div style="color:#A78BFA;font-weight:bold;font-size:1.1em;
                      margin-bottom:8px">📚 {title}</div>
          <div style="color:#E2E8F0;margin-bottom:8px"><b>What:</b> {what}</div>
          <div style="color:#E2E8F0;margin-bottom:8px"><b>Why:</b> {why}</div>
          <div style="background:#2D2B55;padding:10px;border-radius:4px;
                      color:#C4B5FD;font-family:monospace;font-size:0.9em">
            💡 {key_idea}
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def learner_flow(level: str, run_label: str, look_for: str, next_step: str) -> None:
    """Consistent learning workflow banner shown at the top of pages."""
    st.markdown(
        f"""
        <div style="background:#132033;border:1px solid #2B4A6F;border-radius:8px;padding:12px 14px;margin:6px 0 14px 0">
                    <div class="vigil-kicker">{level} learning flow</div>
                    <div class="vigil-step"><b>1. Run:</b> {run_label}</div>
                    <div class="vigil-step"><b>2. Inspect:</b> {look_for}</div>
                    <div style="color:#A7F3D0;font-size:0.9em;margin-top:4px"><b>3. Then:</b> {next_step}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def lesson_objective(level: str, objective: str, success_looks_like: str) -> None:
    """Sticky objective bar so learners always know the point of this page."""
    success = success_looks_like.strip()
    if success:
        success = success[0].upper() + success[1:]
    st.markdown(
        f"""
        <div style="position:sticky;top:0;z-index:10;background:#0F172A;border:1px solid #334155;
                    border-radius:8px;padding:10px 12px;margin:4px 0 14px 0">
          <div style="color:#FDE68A;font-size:0.8em;font-weight:700;letter-spacing:0.03em">CURRENT OBJECTIVE · {level}</div>
          <div style="color:#E2E8F0;font-size:0.95em;margin-top:3px"><b>{objective}</b></div>
          <div style="color:#93C5FD;font-size:0.86em;margin-top:4px"><b>Success check:</b> {success}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def learner_coach(before_run: str, read_output: str, common_miss: str) -> None:
    """Progressive disclosure for guidance without overwhelming the page."""
    with st.expander("🧭 Learner Coach: How to Get the Most From This Page", expanded=False):
        st.markdown(f"**Before you run:** {before_run}")
        st.markdown(f"**How to read the output:** {read_output}")
        st.markdown(f"**Common pitfall:** {common_miss}")


def try_next_cve(level_key: str) -> None:
    """One-click CVE presets to reduce friction between experiments."""
    st.caption("Try another CVE quickly (keep one variable constant as you compare levels).")
    presets = [
        ("CVE-2021-44228", "Log4Shell"),
        ("CVE-2023-44487", "HTTP/2 Rapid Reset"),
        ("CVE-2014-0160", "Heartbleed"),
    ]
    cols = st.columns(3)
    for col, (cve, label) in zip(cols, presets):
        with col:
            if st.button(f"{label}", key=f"{level_key}_{cve}", use_container_width=True):
                st.session_state["vigil_cve"] = cve
                st.success(f"Active CVE set to {cve}")


def result_hint(title: str, text: str, tone: str = "info") -> None:
    """Short interpretation hint to prevent learner confusion."""
    if tone == "success":
        st.success(f"{title}: {text}")
    elif tone == "warning":
        st.warning(f"{title}: {text}")
    else:
        st.info(f"{title}: {text}")


def under_the_hood(code_snippet: str, explanation: str) -> None:
    """Collapsible 'Under the hood' section showing the key code."""
    with st.expander("🔍 Under the hood"):
        st.code(code_snippet, language="python")
        st.caption(explanation)


def cost_line(data: dict) -> None:
    """Show elapsed time + token count + estimated cost from a level response."""
    u = data.get("token_usage") or {}
    if u:
        st.caption(
            f"⏱ {data['elapsed_ms']}ms  ·  "
            f"🔢 {u.get('total_tokens', 0):,} tokens "
            f"({u.get('prompt_tokens', 0):,} in / {u.get('completion_tokens', 0):,} out)  ·  "
            f"💰 ~${u.get('estimated_cost_usd', 0):.4f} USD (est.)"
        )
    else:
        st.caption(f"⏱ {data['elapsed_ms']}ms")

    cache = data.get("cache")
    if cache and isinstance(cache, dict):
        label = "hit" if cache.get("from_cache") else "miss"
        st.caption(f"🧠 Cache: {label}  ·  key {str(cache.get('key', ''))[:12]}...  ·  ttl {cache.get('ttl_seconds', 0)}s")


def cve_input(key: str = "vigil_cve", default: str = "CVE-2021-44228") -> str:
    """Standard CVE input widget.

    Uses one shared session key so the selected CVE persists across every page.
    Only one page renders per run, so reusing the same widget key is safe.
    The ``key`` argument is kept for backwards compatibility but is ignored.
    """
    st.session_state.setdefault("vigil_cve", default)
    return st.text_input(
        "CVE ID",
        key="vigil_cve",
        help="Enter any CVE identifier. Your choice is remembered across pages. "
             "CVE-2021-44228 (Log4Shell) is a good default for testing.",
    )
