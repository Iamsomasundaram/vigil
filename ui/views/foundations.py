"""Foundations pages F4-F16."""

import streamlit as st

from common import (
    COST_NOTE,
    api,
    concept_box,
    cve_input,
    learner_coach,
    learner_flow,
    lesson_objective,
    result_hint,
)


# ─── F4 ───────────────────────────────────────────────────────────────────────

def render_f4() -> None:
    st.title("F4 — Tokenization & Context Economics")
    lesson_objective("F4", "Build intuition for token density and context-window pressure.", "you can estimate which inputs will be expensive or near limits")

    concept_box(
        title="See tokens directly, not just as a billing line",
        what="Tokenize arbitrary text and inspect context usage against model limits.",
        why="Token intuition drives prompt design, RAG chunking, and cost control.",
        key_idea="text -> token count -> context % -> estimated cost",
    )
    learner_flow(
        "F4",
        "Tokenize",
        "token_count, pct_of_context, and sample token pieces",
        "F6 to connect token tradeoffs to prompt quality",
    )
    learner_coach(
        "Compare short prose, JSON, and code snippets.",
        "Use context percentage to reason about headroom before model calls.",
        "Treating character count as equivalent to token count.",
    )

    model = st.text_input("Model", value="gpt-4o-mini", key="f4_model")
    text = st.text_area(
        "Text to tokenize",
        value="CVE-2021-44228 allows remote code execution in vulnerable Log4j deployments.",
        key="f4_text",
        height=140,
    )

    if st.button("Tokenize", type="primary", key="f4_run"):
        data = api("POST", "/foundations/tokenize", json={"text": text, "model": model.strip() or None})
        if data:
            c1, c2, c3 = st.columns(3)
            c1.metric("Token count", data.get("token_count", 0))
            c2.metric("Context limit", data.get("context_limit", 0))
            c3.metric("Est. cost", f"~${data.get('est_cost_usd', 0.0):.6f}", help=COST_NOTE)
            st.progress(min(float(data.get("pct_of_context", 0.0)) / 100.0, 1.0))
            st.caption(f"Prompt occupies {data.get('pct_of_context', 0.0):.4f}% of the context window.")
            st.markdown("#### Sample token pieces")
            st.write(data.get("sample_tokens", []))

# ─── F6 ───────────────────────────────────────────────────────────────────────

def render_f6() -> None:
    st.title("F6 — Prompt Engineering Techniques")
    lesson_objective("F6", "Compare prompt patterns and their token-quality tradeoffs.", "you can pick a technique intentionally for a task and budget")

    concept_box(
        title="Compare prompt techniques on one task",
        what="Run zero-shot, few-shot, chain-of-thought, and self-consistency side-by-side.",
        why="Prompting is the cheapest high-leverage knob before model or infra changes.",
        key_idea="same task + different prompt strategy -> different quality/cost",
    )
    learner_flow(
        "F6",
        "Compare techniques",
        "output differences vs token/cost overhead",
        "E4 to route techniques by provider/cost policy",
    )
    learner_coach(
        "Keep the same CVE and advisory text while comparing techniques.",
        "Read output differences before judging token/cost overhead.",
        "Assuming few-shot or CoT is always best regardless of task complexity.",
    )

    cve_id = cve_input("f6_cve")
    advisory = st.text_area(
        "Optional advisory text (treated as untrusted and fenced)",
        value="Public exploit observed; internet-facing service; patch available.",
        key="f6_text",
        height=120,
    )

    if st.button("Compare techniques", type="primary", key="f6_run"):
        with st.spinner("Running prompt comparisons…"):
            data = api("POST", "/foundations/prompt-compare", json={"cve_id": cve_id, "advisory_text": advisory})
        if data:
            st.dataframe(data.get("results", []), use_container_width=True)
            st.caption(data.get("notes", ""))

# ─── F11 ──────────────────────────────────────────────────────────────────────

def render_f11() -> None:
    st.title("F11 — Retrieval Data Preparation and Index Quality")
    lesson_objective("F11", "Understand how chunking and overlap change retrieval quality.", "you can tune chunk settings and explain ranking differences")

    concept_box(
        title="Data engineering for RAG starts before retrieval",
        what="This lab chunks a small document set and retrieves top hits for your query.",
        why="Many GenAI failures come from weak chunking/indexing choices, not the model itself.",
        key_idea="documents -> chunks(size, overlap) -> ranked hits with evidence overlap",
    )
    learner_flow(
        "F11",
        "Run retrieval lab",
        "hit scores, overlap terms, and chunk count economics",
        "F12 for objective retrieval metrics",
    )
    learner_coach(
        "Start with a short query, then vary only one knob at a time.",
        "Inspect overlap terms and preview text, not score alone.",
        "Changing multiple parameters at once and losing comparability.",
    )

    c1, c2 = st.columns(2)
    query = c1.text_input(
        "Query",
        value="log4j remote code execution patch urgency",
        key="f11_query",
    )
    top_k = c2.slider("Top-k", min_value=1, max_value=10, value=5, key="f11_topk")

    c3, c4 = st.columns(2)
    chunk_size = c3.slider("Chunk size (words)", min_value=20, max_value=200, value=80, step=10, key="f11_chunk")
    overlap = c4.slider("Chunk overlap (words)", min_value=0, max_value=100, value=20, step=5, key="f11_overlap")

    if st.button("Run retrieval lab", type="primary", key="f11_run"):
        with st.spinner("Building index and ranking retrieval hits…"):
            data = api(
                "POST",
                "/foundations/retrieval-lab",
                json={
                    "query": query,
                    "chunk_size_words": chunk_size,
                    "overlap_words": overlap,
                    "top_k": top_k,
                },
            )

        if data:
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Documents", data.get("n_docs", 0))
            m2.metric("Chunks", data.get("n_chunks", 0))
            m3.metric("Avg chunk words", data.get("avg_chunk_words", 0.0))
            m4.metric("Diversity entropy", data.get("diversity_entropy", 0.0))

            hits = data.get("hits", [])
            if not hits:
                st.warning("No hits returned. Try broader query terms.")
            else:
                rows = []
                for i, h in enumerate(hits, 1):
                    rows.append(
                        {
                            "rank": i,
                            "chunk": h.get("chunk_id", "?"),
                            "title": h.get("title", "?"),
                            "score": h.get("score", 0.0),
                            "overlap_terms": ", ".join(h.get("overlap_terms", [])),
                            "preview": h.get("text_preview", ""),
                        }
                    )
                st.dataframe(rows, use_container_width=True)

            result_hint("Interpretation", "If top hits are noisy, adjust chunk size and overlap before changing models.")

# ─── F12 ──────────────────────────────────────────────────────────────────────

def render_f12() -> None:
    st.title("F12 — Retrieval Evaluation Metrics")
    lesson_objective("F12", "Quantify retrieval quality with Recall@k, MRR, and nDCG.", "you can compare two retrieval settings objectively")

    concept_box(
        title="Measure retrieval before changing models",
        what="Run a labeled benchmark and compare two chunking configurations.",
        why="Metrics make retrieval changes objective instead of guesswork.",
        key_idea="same dataset -> setting A vs B -> Recall@k, MRR, nDCG deltas",
    )
    learner_flow(
        "F12",
        "Run retrieval evaluation",
        "summary metrics and per-query wins/losses",
        "choose the winning setting and retest after data changes",
    )
    learner_coach(
        "Change one setting at a time between A and B.",
        "Prioritize MRR/nDCG for ranking quality, not just Recall@k.",
        "Treating one metric increase as overall improvement when others regress.",
    )

    c1, c2 = st.columns(2)
    dataset_path = c1.text_input("Dataset path", value="data/eval/retrieval_golden.json", key="f12_dataset")
    k = c2.slider("k", min_value=1, max_value=10, value=5, key="f12_k")

    st.markdown("### Setting A")
    a1, a2 = st.columns(2)
    chunk_a = a1.slider("Chunk size A", min_value=20, max_value=200, value=80, step=10, key="f12_chunk_a")
    overlap_a = a2.slider("Overlap A", min_value=0, max_value=100, value=20, step=5, key="f12_overlap_a")

    st.markdown("### Setting B")
    b1, b2 = st.columns(2)
    chunk_b = b1.slider("Chunk size B", min_value=20, max_value=200, value=120, step=10, key="f12_chunk_b")
    overlap_b = b2.slider("Overlap B", min_value=0, max_value=100, value=20, step=5, key="f12_overlap_b")

    if st.button("Run retrieval evaluation", type="primary", key="f12_run"):
        with st.spinner("Evaluating retrieval settings on labeled queries…"):
            data = api(
                "POST",
                "/foundations/retrieval-eval",
                json={
                    "dataset_path": dataset_path,
                    "k": k,
                    "chunk_size_a": chunk_a,
                    "overlap_a": overlap_a,
                    "chunk_size_b": chunk_b,
                    "overlap_b": overlap_b,
                },
            )

        if data:
            sa = data.get("summary_a", {})
            sb = data.get("summary_b", {})
            winner = data.get("winner", "tie")
            result_hint("Winner", "Setting A" if winner == "a" else ("Setting B" if winner == "b" else "Tie"), tone="success")

            rows = [
                {"setting": "A", "recall@k": sa.get("recall_at_k", 0.0), "mrr@k": sa.get("mrr_at_k", 0.0), "ndcg@k": sa.get("ndcg_at_k", 0.0)},
                {"setting": "B", "recall@k": sb.get("recall_at_k", 0.0), "mrr@k": sb.get("mrr_at_k", 0.0), "ndcg@k": sb.get("ndcg_at_k", 0.0)},
            ]
            st.dataframe(rows, use_container_width=True)

            case_rows = []
            for case in data.get("cases", []):
                case_rows.append(
                    {
                        "query": case.get("query", ""),
                        "A_recall": case.get("a", {}).get("recall_at_k", 0.0),
                        "A_mrr": case.get("a", {}).get("mrr_at_k", 0.0),
                        "A_ndcg": case.get("a", {}).get("ndcg_at_k", 0.0),
                        "B_recall": case.get("b", {}).get("recall_at_k", 0.0),
                        "B_mrr": case.get("b", {}).get("mrr_at_k", 0.0),
                        "B_ndcg": case.get("b", {}).get("ndcg_at_k", 0.0),
                    }
                )
            st.markdown("### Per-query breakdown")
            st.dataframe(case_rows, use_container_width=True)
            result_hint("Interpretation", "Pick the setting with stronger MRR/nDCG unless recall requirements dictate otherwise.")

# ─── F13 ──────────────────────────────────────────────────────────────────────

def render_f13() -> None:
    st.title("F13 — Factuality and Citation Verification")
    lesson_objective("F13", "Check whether claims are actually supported by evidence.", "you can flag unsupported claims and decide when to abstain")

    concept_box(
        title="Fluent text is not always faithful",
        what="Paste an answer and evidence snippets to verify claim support.",
        why="Grounded systems should abstain when claims cannot be supported by evidence.",
        key_idea="answer -> claim split -> support check against evidence -> faithfulness score",
    )
    learner_flow(
        "F13",
        "Run factuality check",
        "faithfulness score, unsupported claims, abstain recommendation",
        "tighten claims or improve retrieval evidence and rerun",
    )
    learner_coach(
        "Use the same answer text while changing evidence quality.",
        "Pay attention to unsupported claims list before trusting summary quality.",
        "Assuming confident tone means evidence-backed truth.",
    )

    answer_text = st.text_area(
        "Answer text to verify",
        value=(
            "Log4j allows remote code execution. Patch 2.17.1 is available. "
            "This exploit affects all network routers globally."
        ),
        key="f13_answer",
        height=130,
    )
    evidence_blob = st.text_area(
        "Evidence snippets (one per line)",
        value=(
            "CVE-2021-44228 allows remote code execution in Apache Log4j.\n"
            "Patch to Log4j 2.17.1 or later is recommended."
        ),
        key="f13_evidence",
        height=120,
    )
    threshold = st.slider("Support threshold", min_value=0.1, max_value=0.9, value=0.45, step=0.05, key="f13_threshold")

    if st.button("Run factuality check", type="primary", key="f13_run"):
        evidence_snippets = [line.strip() for line in evidence_blob.splitlines() if line.strip()]
        with st.spinner("Evaluating claim support against evidence…"):
            data = api(
                "POST",
                "/foundations/factuality-check",
                json={
                    "answer_text": answer_text,
                    "evidence_snippets": evidence_snippets,
                    "support_threshold": threshold,
                },
            )

        if data:
            m1, m2, m3 = st.columns(3)
            m1.metric("Faithfulness", data.get("faithfulness_score", 0.0))
            m2.metric("Supported", f"{data.get('supported_claims', 0)} / {data.get('total_claims', 0)}")
            m3.metric("Abstain recommended", "Yes" if data.get("abstain_recommended") else "No")

            unsupported = data.get("unsupported_claims", [])
            if unsupported:
                st.warning("Unsupported claims detected")
                for claim in unsupported:
                    st.markdown(f"- {claim}")

            rows = []
            for row in data.get("results", []):
                rows.append(
                    {
                        "claim": row.get("claim", ""),
                        "supported": row.get("supported", False),
                        "support_score": row.get("support_score", 0.0),
                        "evidence_excerpt": row.get("evidence_excerpt", ""),
                    }
                )
            st.dataframe(rows, use_container_width=True)
            result_hint("Interpretation", "When unsupported claims remain, revise output or abstain.", tone="warning")

# ─── F14 ──────────────────────────────────────────────────────────────────────

def render_f14() -> None:
    st.title("F14 — Prompt Lifecycle and Experiments")
    lesson_objective("F14", "Compare prompt versions on fixed tasks and decide ship or hold.", "you can justify a winner from replay metrics")

    concept_box(
        title="Prompting as a managed lifecycle",
        what="List prompt versions and compare them on a fixed replay set.",
        why="Versioning and replay prevent subjective prompt changes from reaching production.",
        key_idea="version A vs B on same items -> quality summary -> promote or hold",
    )
    learner_flow(
        "F14",
        "Compare versions",
        "avg quality, per-item wins, and tie cases",
        "promote only if gains are stable across items",
    )
    learner_coach(
        "Keep the replay set fixed while changing prompt versions.",
        "Check per-item outcomes before trusting overall average.",
        "Promoting a prompt from one good example instead of a replay set.",
    )

    versions = api("GET", "/foundations/prompt-versions") or []
    version_ids = [v.get("id", "") for v in versions if v.get("id")]
    if not version_ids:
        st.warning("No prompt versions found.")
    else:
        c1, c2 = st.columns(2)
        version_a = c1.selectbox("Version A", version_ids, index=0, key="f14_a")
        version_b = c2.selectbox("Version B", version_ids, index=min(1, len(version_ids) - 1), key="f14_b")

        items_blob = st.text_area(
            "Replay items (one per line)",
            value="CVE-2021-44228\nCVE-2023-44487\nCVE-2014-0160",
            key="f14_items",
            height=110,
        )
        items = [x.strip() for x in items_blob.splitlines() if x.strip()]

        if st.button("Compare prompt versions", type="primary", key="f14_run"):
            with st.spinner("Running deterministic replay comparison…"):
                data = api(
                    "POST",
                    "/foundations/prompt-versions/compare",
                    json={
                        "version_a": version_a,
                        "version_b": version_b,
                        "items": items,
                    },
                )

            if data:
                summary = data.get("summary", {})
                m1, m2, m3 = st.columns(3)
                m1.metric("A avg", summary.get("a_avg_quality", 0.0))
                m2.metric("B avg", summary.get("b_avg_quality", 0.0))
                m3.metric("Winner", data.get("overall_winner", "tie"))

                st.dataframe(data.get("per_item", []), use_container_width=True)
                result_hint("Interpretation", "Promote only if the winner is consistent across most items.")

# ─── F15 ──────────────────────────────────────────────────────────────────────

def render_f15() -> None:
    st.title("F15 — Privacy and Safe Logging")
    lesson_objective("F15", "Redact sensitive content before model calls and logging.", "you can produce a safe log snapshot without leaking secrets")

    concept_box(
        title="Privacy controls are part of GenAI quality",
        what="Detect and redact common sensitive patterns from input and nested logs.",
        why="Safe systems preserve debugging value while preventing data leakage.",
        key_idea="raw text -> redaction findings -> redacted text + safe log snapshot",
    )
    learner_flow(
        "F15",
        "Run privacy redaction",
        "findings, changed flag, and sanitized payload",
        "integrate this before any external model/tool calls",
    )
    learner_coach(
        "Paste realistic strings containing emails, IPs, or tokens.",
        "Validate both redacted text and safe nested snapshot output.",
        "Only sanitizing display text but logging raw payloads elsewhere.",
    )

    text = st.text_area(
        "Text to sanitize",
        value="Contact ops@example.com from 10.20.30.40 using token=abc123 and key sk-demo-1234567890123456",
        key="f15_text",
        height=120,
    )

    if st.button("Run privacy redaction", type="primary", key="f15_run"):
        with st.spinner("Redacting sensitive patterns…"):
            data = api("POST", "/foundations/privacy/redact", json={"text": text})
        if data:
            m1, m2 = st.columns(2)
            m1.metric("Changed", "Yes" if data.get("changed") else "No")
            m2.metric("Findings", len(data.get("findings", [])))
            st.markdown("### Redacted text")
            st.code(data.get("redacted_text", ""))
            st.markdown("### Safe log snapshot")
            st.json(data.get("safe_log_snapshot", {}))
            result_hint("Interpretation", "Redact before sending to LLMs and before persisting traces.")

# ─── F16 ──────────────────────────────────────────────────────────────────────

def render_f16() -> None:
    st.title("F16 — Hybrid Retrieval & Reranking")
    lesson_objective("F16", "See how lexical, vector, and hybrid retrieval differ, and how reranking helps.", "you can pick a retrieval strategy from evidence")

    concept_box(
        title="Production RAG rarely uses one retriever",
        what="Compare lexical, vector, and fused hybrid retrieval, with optional reranking.",
        why="Hybrid retrieval plus reranking is the industry-standard path to better top-k quality.",
        key_idea="lexical + vector -> fused score -> optional rerank -> better ranking",
    )
    learner_flow(
        "F16",
        "Run hybrid retrieval",
        "how hybrid and rerank reorder the top hits vs single-mode",
        "F12 to quantify which setting is objectively better",
    )
    learner_coach(
        "Adjust alpha to shift lexical vs vector weight.",
        "Compare the three result lists side by side, not just the top hit.",
        "Assuming vector search always beats lexical for keyword-heavy queries.",
    )

    c1, c2 = st.columns(2)
    query = c1.text_input("Query", value="log4j remote code execution patch urgency", key="f16_query")
    top_k = c2.slider("Top-k", min_value=1, max_value=10, value=5, key="f16_topk")

    c3, c4 = st.columns(2)
    alpha = c3.slider("Alpha (lexical weight)", min_value=0.0, max_value=1.0, value=0.5, step=0.1, key="f16_alpha")
    rerank = c4.checkbox("Apply reranking", value=True, key="f16_rerank")

    if st.button("Run hybrid retrieval", type="primary", key="f16_run"):
        with st.spinner("Running lexical, vector, and hybrid retrieval…"):
            data = api(
                "POST",
                "/foundations/hybrid-retrieval",
                json={"query": query, "alpha": alpha, "rerank": rerank, "top_k": top_k},
            )
        if data:
            def _rows(hits):
                return [
                    {
                        "chunk": h.get("chunk_id", "?"),
                        "doc": h.get("doc_id", "?"),
                        "lexical": h.get("lexical_score", 0.0),
                        "vector": h.get("vector_score", 0.0),
                        "fused": h.get("fused_score", 0.0),
                        "rerank": h.get("rerank_score"),
                        "score": h.get("score", 0.0),
                    }
                    for h in hits
                ]

            st.markdown("### Lexical")
            st.dataframe(_rows(data.get("lexical_hits", [])), use_container_width=True)
            st.markdown("### Vector")
            st.dataframe(_rows(data.get("vector_hits", [])), use_container_width=True)
            st.markdown("### Hybrid" + (" + rerank" if rerank else ""))
            st.dataframe(_rows(data.get("hybrid_hits", [])), use_container_width=True)
            result_hint("Interpretation", "Prefer the mode whose top hits best match the intended answer, then confirm with F12 metrics.")
