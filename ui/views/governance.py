"""Governance and ops pages F17-F20, F23, F24."""

import streamlit as st

from common import (
    api,
    concept_box,
    learner_coach,
    learner_flow,
    lesson_objective,
    result_hint,
)


# ─── F17 ──────────────────────────────────────────────────────────────────────

def render_f17() -> None:
    st.title("F17 — Online Evaluation & Drift Monitoring")
    lesson_objective("F17", "Monitor live quality/latency/cost and detect sustained drift.", "you can decide when to investigate or roll back")

    concept_box(
        title="Offline evals are not enough",
        what="Record live samples into a rolling window, then compute drift and SLO breaches.",
        why="Production quality decays silently; online monitoring catches regressions early.",
        key_idea="rolling samples -> drift + SLO breach -> action recommendation",
    )
    learner_flow(
        "F17",
        "Add samples and compute drift",
        "avg quality, breaches, and sustained-drift flag",
        "F20 to gate rollout when drift breaches SLOs",
    )
    learner_coach(
        "Add a batch of samples first, then request the drift report.",
        "Distinguish a single bad sample from sustained drift.",
        "Reacting to noise instead of a sustained downward trend.",
    )

    c1, c2, c3 = st.columns(3)
    q = c1.slider("Sample quality", 0.0, 1.0, 0.6, 0.05, key="f17_q")
    lat = c2.number_input("Latency ms", min_value=0.0, value=1200.0, key="f17_lat")
    cost = c3.number_input("Cost USD", min_value=0.0, value=0.004, format="%.4f", key="f17_cost")

    cc1, cc2 = st.columns(2)
    if cc1.button("Add 5 samples", key="f17_add"):
        for _ in range(5):
            api("POST", "/reliability/drift/sample", json={"quality": q, "latency_ms": lat, "cost_usd": cost})
        st.success("Added 5 samples to the rolling window.")

    if cc2.button("Compute drift report", type="primary", key="f17_run"):
        data = api("POST", "/reliability/drift/report", json={"baseline_quality": 0.8})
        if data:
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Samples", data.get("n_samples", 0))
            m2.metric("Avg quality", data.get("avg_quality", 0.0))
            m3.metric("Drift", data.get("quality_drift", 0.0))
            m4.metric("Action", data.get("recommended_action", "?"))
            breaches = data.get("breaches", [])
            if breaches:
                st.warning("SLO breaches: " + ", ".join(breaches))
            if data.get("sustained_drift"):
                st.error("Sustained drift detected — investigate or roll back.")
            result_hint("Interpretation", "Rollback/human-review is warranted when quality breaches SLO or drift is sustained.")

# ─── F18 ──────────────────────────────────────────────────────────────────────

def render_f18() -> None:
    st.title("F18 — Agent Permissions & Action Governance")
    lesson_objective("F18", "Enforce least-privilege tool access and sandbox limits.", "you can explain why an action is allowed, denied, or needs approval")

    concept_box(
        title="Autonomy needs guardrails on actions",
        what="Check a proposed tool action against role scope, sandbox limit, and approval rules.",
        why="Least-privilege and sandboxing prevent unsafe agent actions in production.",
        key_idea="role + tool + sandbox -> allow / deny / require approval",
    )
    learner_flow(
        "F18",
        "Check an action",
        "allowed flag, effective sandbox, and reasons",
        "combine with F20 rollback for full action safety",
    )
    learner_coach(
        "Try the same tool across viewer, analyst, and responder roles.",
        "Notice when execute mode requires human approval.",
        "Granting execute scope where simulate would be sufficient.",
    )

    c1, c2 = st.columns(2)
    role = c1.selectbox("Role", ["viewer", "analyst", "responder"], key="f18_role")
    tool = c2.selectbox("Tool", ["fetch_nvd_data", "fetch_epss_score", "open_ticket", "apply_patch"], key="f18_tool")
    c3, c4 = st.columns(2)
    sandbox = c3.selectbox("Sandbox", ["read_only", "simulate", "execute"], index=2, key="f18_sandbox")
    approved = c4.checkbox("Human approved", value=False, key="f18_approved")

    if st.button("Check action", type="primary", key="f18_run"):
        data = api(
            "POST",
            "/reliability/action/check",
            json={"role": role, "tool": tool, "requested_sandbox": sandbox, "approved": approved},
        )
        if data:
            m1, m2, m3 = st.columns(3)
            m1.metric("Allowed", "Yes" if data.get("allowed") else "No")
            m2.metric("Effective sandbox", data.get("effective_sandbox", "?"))
            m3.metric("Needs approval", "Yes" if data.get("requires_approval") else "No")
            st.markdown("**Reasons:** " + ", ".join(data.get("reasons", [])))
            tone = "success" if data.get("allowed") else "warning"
            result_hint("Interpretation", "Denied actions never execute; approvals gate sensitive execute-mode actions.", tone=tone)

# ─── F19 ──────────────────────────────────────────────────────────────────────

def render_f19() -> None:
    st.title("F19 — AI Supply Chain & Provenance")
    lesson_objective("F19", "Verify integrity of prompts, model policies, and tool schemas.", "you can block promotion when artifacts fail integrity or evals")

    concept_box(
        title="Prompts and configs are supply-chain assets",
        what="Verify tracked AI artifacts against recorded checksums and gate promotion.",
        why="Tampering or drift in prompts/tools/configs introduces silent production risk.",
        key_idea="manifest -> checksum verify -> promotion gate (integrity + evals)",
    )
    learner_flow(
        "F19",
        "Verify artifacts and test promotion",
        "integrity status and promotion decision",
        "F20 to stage the promoted change safely",
    )
    learner_coach(
        "Verify first, then test promotion with eval pass/fail.",
        "Read per-artifact verification, not just the overall flag.",
        "Promoting changes without provenance or integrity checks.",
    )

    if st.button("Verify artifacts", type="primary", key="f19_verify"):
        data = api("GET", "/reliability/supply-chain/verify")
        if data:
            m1, m2, m3 = st.columns(3)
            m1.metric("Artifacts", data.get("n_artifacts", 0))
            m2.metric("Violations", data.get("violations", 0))
            m3.metric("Integrity", "OK" if data.get("integrity_ok") else "FAILED")
            st.dataframe(data.get("artifacts", []), use_container_width=True)

    eval_passed = st.checkbox("Evals passed", value=True, key="f19_eval")
    if st.button("Test promotion gate", key="f19_promote"):
        data = api("POST", "/reliability/supply-chain/promote", json={"eval_passed": eval_passed})
        if data:
            allowed = data.get("allowed", False)
            result_hint(
                "Promotion",
                "Allowed" if allowed else "Blocked: " + ", ".join(data.get("reasons", [])),
                tone="success" if allowed else "warning",
            )

# ─── F20 ──────────────────────────────────────────────────────────────────────

def render_f20() -> None:
    st.title("F20 — Release Safety: Shadow, Canary & Rollback")
    lesson_objective("F20", "Compare control vs treatment and decide promote/hold/rollback.", "you can trigger rollback from objective guardrails")

    concept_box(
        title="Ship changes with a blast-radius limit",
        what="Compare canary treatment quality against control and apply a rollback guardrail.",
        why="Staged rollout with rollback is the safe way to change prompts, models, or retrieval.",
        key_idea="control vs treatment -> delta vs min_delta -> promote / hold / rollback",
    )
    learner_flow(
        "F20",
        "Evaluate a rollout",
        "delta and decision (promote/hold/rollback)",
        "wire this to F17 drift alerts for automatic rollback",
    )
    learner_coach(
        "Enter realistic control and treatment quality scores.",
        "Watch how a small regression trips the rollback guardrail.",
        "Promoting on a noisy improvement without enough samples.",
    )

    c1, c2 = st.columns(2)
    control_csv = c1.text_input("Control scores (comma)", value="0.80,0.82,0.79", key="f20_control")
    treatment_csv = c2.text_input("Treatment scores (comma)", value="0.74,0.71,0.70", key="f20_treatment")
    min_delta = st.slider("Min acceptable delta", -0.2, 0.0, -0.02, 0.01, key="f20_delta")

    if st.button("Evaluate rollout", type="primary", key="f20_run"):
        control = [float(x) for x in control_csv.split(",") if x.strip()]
        treatment = [float(x) for x in treatment_csv.split(",") if x.strip()]
        data = api(
            "POST",
            "/reliability/release/evaluate",
            json={"control_scores": control, "treatment_scores": treatment, "min_delta": min_delta},
        )
        if data:
            m1, m2, m3 = st.columns(3)
            m1.metric("Control avg", data.get("control_avg", 0.0))
            m2.metric("Treatment avg", data.get("treatment_avg", 0.0))
            m3.metric("Delta", data.get("delta", 0.0))
            decision = data.get("decision", "hold")
            tone = "success" if decision == "promote" else ("warning" if decision == "hold" else "warning")
            result_hint("Decision", decision.upper() + " (next stage: " + str(data.get("next_stage", "?")) + ")", tone=tone)

# ─── F23 ──────────────────────────────────────────────────────────────────────

def render_f23() -> None:
    st.title("F23 — Responsible-AI Evaluation")
    lesson_objective("F23", "Screen output for policy violations and check outcome fairness.", "you can decide if a batch is safe to ship")

    concept_box(
        title="Safety is moderation plus fairness",
        what="Run content moderation on outputs and a demographic-parity check on outcomes.",
        why="Responsible-AI gates catch harmful content and biased outcomes before release.",
        key_idea="texts -> moderation flags; outcomes -> 80% rule -> safe-to-ship",
    )
    learner_flow(
        "F23",
        "Run responsible-AI check",
        "flagged categories and disparate-impact ratio",
        "gate releases (F20) on this safe-to-ship signal",
    )
    learner_coach(
        "Test clean and clearly harmful text side by side.",
        "Read the disparate-impact ratio, not just per-group rates.",
        "Shipping when moderation is clean but fairness fails the 80% rule.",
    )

    texts_blob = st.text_area(
        "Output samples (one per line)",
        value="This CVE analysis is clear and helpful\nYou stupid loser",
        key="f23_texts",
        height=110,
    )
    st.caption("Outcomes: group,positive per line (positive = 1/0)")
    outcomes_blob = st.text_area(
        "Outcomes (group,positive)",
        value="group_a,1\ngroup_a,1\ngroup_b,0\ngroup_b,0",
        key="f23_outcomes",
        height=110,
    )

    if st.button("Run responsible-AI check", type="primary", key="f23_run"):
        texts = [t.strip() for t in texts_blob.splitlines() if t.strip()]
        outcomes = []
        for line in outcomes_blob.splitlines():
            parts = [p.strip() for p in line.split(",")]
            if len(parts) == 2:
                outcomes.append({"group": parts[0], "positive": parts[1] in ("1", "true", "True")})

        data = api("POST", "/foundations/responsible-ai", json={"texts": texts, "outcomes": outcomes})
        if data:
            m1, m2, m3 = st.columns(3)
            m1.metric("Texts flagged", f"{data.get('flagged_texts', 0)} / {data.get('n_texts', 0)}")
            fairness = data.get("fairness", {})
            m2.metric("Disparate impact", fairness.get("disparate_impact_ratio", 0.0))
            m3.metric("Safe to ship", "Yes" if data.get("safe_to_ship") else "No")

            flagged = [m for m in data.get("moderation", []) if m.get("flagged")]
            if flagged:
                st.warning("Flagged content")
                st.dataframe(
                    [{"text": m["text"], "categories": ", ".join(m["categories"])} for m in flagged],
                    use_container_width=True,
                )
            st.markdown("**Group selection rates:** " + ", ".join(f"{g}={r}" for g, r in fairness.get("groups", {}).items()))
            if not fairness.get("passes_80pct_rule", True):
                st.error("Fails the 80% rule — potential disparate impact.")
            result_hint("Interpretation", "Ship only when moderation is clean AND fairness passes the 80% rule.", tone="warning" if not data.get("safe_to_ship") else "success")

# ─── F24 ──────────────────────────────────────────────────────────────────────

def render_f24() -> None:
    st.title("F24 — Semantic Caching")
    lesson_objective("F24", "Serve cached answers for semantically similar queries.", "you can explain semantic vs exact-key caching tradeoffs")

    concept_box(
        title="Cache meaning, not just exact keys",
        what="Replay queries through a similarity cache; near-duplicate wording reuses answers.",
        why="Semantic caching cuts cost/latency where exact-key caches miss on paraphrases.",
        key_idea="query terms -> cosine similarity -> hit if >= threshold",
    )
    learner_flow(
        "F24",
        "Simulate the cache",
        "per-query hit/miss and overall hit rate",
        "tune threshold to balance reuse vs false hits",
    )
    learner_coach(
        "Include paraphrased duplicates to see semantic hits.",
        "Watch how threshold changes hit rate and false positives.",
        "Setting the threshold so low that unrelated queries hit.",
    )

    threshold = st.slider("Similarity threshold", 0.1, 1.0, 0.6, 0.05, key="f24_threshold")
    pairs_blob = st.text_area(
        "Query|response pairs (one per line)",
        value=(
            "What is CVE-2021-44228?|Log4Shell RCE\n"
            "Tell me about CVE-2021-44228|Log4Shell RCE\n"
            "How do I bake bread?|Use flour and yeast"
        ),
        key="f24_pairs",
        height=130,
    )

    if st.button("Simulate semantic cache", type="primary", key="f24_run"):
        pairs = []
        for line in pairs_blob.splitlines():
            if "|" in line:
                q, r = line.split("|", 1)
                pairs.append({"query": q.strip(), "response": r.strip()})

        data = api("POST", "/foundations/semantic-cache", json={"pairs": pairs, "threshold": threshold})
        if data:
            stats = data.get("stats", {})
            m1, m2, m3 = st.columns(3)
            m1.metric("Hits", stats.get("hits", 0))
            m2.metric("Misses", stats.get("misses", 0))
            m3.metric("Hit rate", stats.get("hit_rate", 0.0))
            st.dataframe(data.get("trace", []), use_container_width=True)
            result_hint("Interpretation", "Higher threshold = fewer but safer hits; lower = more reuse but risk of wrong answers.")
