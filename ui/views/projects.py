"""Projects: the P1 autonomous tester and its demo shop."""

import httpx
import streamlit as st

from common import DEMO_SHOP_HEALTH_URL, DEMO_SHOP_URL, concept_box


def _shop_reachable() -> bool:
    try:
        return httpx.get(f"{DEMO_SHOP_HEALTH_URL}/health", timeout=2.0).status_code == 200
    except httpx.HTTPError:
        return False


def render_p1() -> None:
    st.title("P1 — Autonomous Tester")

    concept_box(
        title="A tester that does what a manual tester does, measured against known bugs",
        what="It reads a plain-language test case, checks a web app, notices things the case never mentioned, "
             "and decides whether a failure is an app defect, a bad test, bad data or a broken environment.",
        why="Real systems fail in ways the test cases do not predict. A demo shop with seeded bugs gives an "
            "answer key, so you can say exactly what a tester found, missed or invented.",
        key_idea="plain-language cases + a shop with known bugs + a scorer = trust you can measure",
    )

    st.markdown("### Status")
    st.table(
        {
            "Phase": ["P1.1", "P1.2", "P1.3", "P1.4", "P1.5"],
            "What": [
                "Demo shop, seeded bugs, answer key, scorer",
                "Scope contract, heuristics, observation-only scan",
                "Strategy, classifier with confidence, re-triage, review queue",
                "Codex integration, guard, agency modes, audit",
                "Guide section, UI page, API route",
            ],
            "State": ["Done", "Not started", "Not started", "Not started", "Not started"],
        }
    )
    st.caption("The live tester agent arrives in later phases. Today you can explore the shop and score runs by hand.")

    st.markdown("### Try the demo shop")
    reachable = _shop_reachable()
    if reachable:
        st.success("Demo shop is running.")
    else:
        st.warning("Demo shop is not reachable from here. With Docker Compose it starts with the stack.")
    st.link_button("Open the demo shop", DEMO_SHOP_URL, disabled=not reachable)

    st.markdown(
        "Use it like a customer and write down what looks wrong, then compare with the answer key in "
        "`projects/autonomous_tester/evals/seeded_bugs.yaml`. **Try it before you read the key.**"
    )
    st.markdown("**Switch the shop's profile** (Docker Compose):")
    st.code("SHOP_PROFILE=clean docker compose up -d demo-shop     # the correct shop\n"
            "SHOP_PROFILE=all_bugs docker compose up -d demo-shop  # default: app, data and exploratory issues\n"
            "SHOP_PROFILE=env_down docker compose up -d demo-shop  # cart returns 503, slow pages\n"
            "SHOP_PROFILE=v2_markup docker compose up -d demo-shop # same behaviour, renamed markup",
            language="bash")
    st.caption("Profiles: clean, all_bugs, env_down, v2_markup. The shop is deliberately broken; it is bound to localhost only.")
