"""Glossary page."""

import streamlit as st


# ─── GLOSSARY ─────────────────────────────────────────────────────────────────

def render_glossary() -> None:
    st.title("📖 Glossary")
    st.caption("Key concepts used throughout Vigil — from LLM basics to production patterns.")

    TERMS = [
        {
            "category": "LLM Fundamentals",
            "terms": [
                {
                    "term": "LLM (Large Language Model)",
                    "definition": "A neural network trained on vast text data to predict and generate human-like text. GPT-4o-mini is the LLM powering Vigil.",
                    "example": "client.chat.completions.create(...) — every level call hits an LLM.",
                    "level": None,
                },
                {
                    "term": "Token",
                    "definition": "The unit an LLM reads and writes. One token ≈ 4 characters in English. 'CVE-2021-44228' is ~6 tokens. Cost is billed per token.",
                    "example": "max_tokens=600 caps L0's response at ~450 words.",
                    "level": "L0",
                },
                {
                    "term": "System Prompt",
                    "definition": "Instructions that define the model's role, tone, and constraints before any user message. Think of it as the job description you hand the model.",
                    "example": '"You are a senior cybersecurity analyst..." — L0 system prompt.',
                    "level": "L0",
                },
                {
                    "term": "Temperature",
                    "definition": "Controls randomness. 0.0 = always picks the most likely next token (deterministic). 1.0 = more creative variation. Security analysis uses 0.1–0.2.",
                    "example": "temperature=0.1 across L1–L6 for consistent, precise analysis.",
                    "level": "L0",
                },
                {
                    "term": "Structured Output / JSON Schema",
                    "definition": "Forcing the LLM to return JSON that matches an exact schema instead of free-form text. Makes the response machine-processable and type-safe.",
                    "example": 'response_format={"type": "json_schema", "json_schema": {...}}',
                    "level": "L1",
                },
                {
                    "term": "Pydantic",
                    "definition": "Python library that defines data schemas and validates JSON against them. Used in every Vigil level to parse and validate LLM responses.",
                    "example": "class CVESummary(BaseModel): cvss_score: float = Field(ge=0, le=10)",
                    "level": "L1",
                },
            ],
        },
        {
            "category": "Agent Patterns",
            "terms": [
                {
                    "term": "Prompt Chain",
                    "definition": "A sequence of LLM calls where each step's output becomes input to the next. Produces better results than one large prompt because each step focuses on one job.",
                    "example": "summary → risk_assessment → remediation_plan in L1.",
                    "level": "L1",
                },
                {
                    "term": "Fan-out (Parallel Agents)",
                    "definition": "Sending the same input to multiple agents simultaneously using asyncio.gather(). Total time = slowest single agent, not sum of all agents.",
                    "example": "4 specialist agents run in parallel in L2. ~3s instead of ~12s.",
                    "level": "L2",
                },
                {
                    "term": "Router Pattern",
                    "definition": "An LLM that reads the input and decides WHICH pipeline to run. Its structured output (a Literal field) is used directly as a Python dict key.",
                    "example": "TRACK_HANDLERS[routing.track](cve_id, routing) in L3.",
                    "level": "L3",
                },
                {
                    "term": "ReAct Loop",
                    "definition": "Reason → Act → Observe → Reason → Act → ... The model reasons about what data it needs, calls a tool, reads the result, and decides what to do next.",
                    "example": "The tool-calling while loop in L4 — model calls NVD then EPSS then produces analysis.",
                    "level": "L4",
                },
                {
                    "term": "Tool Use / Function Calling",
                    "definition": "The model emits a structured tool_call message instead of text. Your code executes the real function and returns the result to the model. The model never directly calls code.",
                    "example": "fetch_nvd_data and fetch_epss_score defined in TOOLS list in L4.",
                    "level": "L4",
                },
                {
                    "term": "Grounding",
                    "definition": "Anchoring model outputs to verifiable external data rather than training memory. Grounded facts can be traced to a real API call. Ungrounded facts can be hallucinated.",
                    "example": "L4 injects live NVD/EPSS data into the conversation before asking for analysis.",
                    "level": "L4",
                },
                {
                    "term": "Autonomous Agent",
                    "definition": "An agent that initiates action on its own goals without being prompted by a human each time. L6 monitors CVEs on a schedule and generates alerts while you sleep.",
                    "example": "_monitor_loop() runs as an asyncio.Task, scanning every hour autonomously.",
                    "level": "L6",
                },
            ],
        },
        {
            "category": "Memory & State",
            "terms": [
                {
                    "term": "In-Context Learning",
                    "definition": "Injecting information directly into the prompt so the model reasons about it — no fine-tuning, no embeddings. Vigil's memory system uses this: history is formatted as text and prepended to the system prompt.",
                    "example": "build_memory_context(history) formats DB rows into text for L5's system prompt.",
                    "level": "L5",
                },
                {
                    "term": "Episodic Memory",
                    "definition": "Storing a record of past events (what the agent did, when, and what it found) so future runs can reference them. Vigil stores every CVE analysis in PostgreSQL.",
                    "example": "analyses table in L5 — every run is stored with timestamp and tool log.",
                    "level": "L5",
                },
                {
                    "term": "Feedback Loop",
                    "definition": "Recording the real-world outcome of an agent's recommendation so future runs can account for it. 'We patched this on day 5' changes what the agent recommends on day 30.",
                    "example": "POST /l5/feedback — record patched/dismissed/in_progress outcomes.",
                    "level": "L5",
                },
                {
                    "term": "Short-term vs Long-term Memory",
                    "definition": "Short-term: the messages list within one run (the model sees everything in the current conversation). Long-term: PostgreSQL rows that persist across restarts and are recalled on future runs.",
                    "example": "L4 messages list = short-term. L5 analyses table = long-term.",
                    "level": "L5",
                },
            ],
        },
        {
            "category": "Safety & Production",
            "terms": [
                {
                    "term": "Kill Switch",
                    "definition": "An emergency stop that immediately cancels autonomous agent activity. Essential for any system that acts without human prompting. Must work instantly, not at the end of the next sleep cycle.",
                    "example": "POST /l6/monitor/stop — sets _stop_event and cancels the asyncio.Task immediately.",
                    "level": "L6",
                },
                {
                    "term": "Human Oversight",
                    "definition": "Mechanisms that keep humans in control of autonomous agents: kill switches, alert acknowledgement, escalation tracks, approval gates. The antidote to runaway automation.",
                    "example": "L3's needs_human_review track, L6's kill switch, and alert acknowledgement.",
                    "level": "L3–L6",
                },
                {
                    "term": "Hallucination",
                    "definition": "When an LLM generates plausible-sounding but factually incorrect information. Especially dangerous for security data — a hallucinated CVSS score or patch status can cause real harm.",
                    "example": "L0–L3 rely on training memory (hallucination risk). L4+ use live APIs (grounded).",
                    "level": "L4",
                },
                {
                    "term": "Deterministic vs Probabilistic",
                    "definition": "Deterministic code always produces the same output for the same input (e.g. change detection thresholds). Probabilistic LLM calls may vary. Good agents use deterministic logic for decisions, LLMs for communication.",
                    "example": "detect_changes() is deterministic code. generate_alert() is the LLM's job.",
                    "level": "L6",
                },
                {
                    "term": "EPSS (Exploit Prediction Scoring System)",
                    "definition": "A daily-updated score (0–1) representing the probability that a CVE will be exploited in the next 30 days. Complements CVSS — a CVSS 9.0 with EPSS 0.001 is less urgent than a CVSS 6.0 with EPSS 0.85.",
                    "example": "fetch_epss_score() in L4/L5/L6. EPSS spike ≥0.15 triggers an L6 alert.",
                    "level": "L4",
                },
                {
                    "term": "CVSS (Common Vulnerability Scoring System)",
                    "definition": "A 0–10 score rating the inherent severity of a vulnerability based on its characteristics (attack vector, complexity, impact). Does NOT measure exploitation likelihood — that's EPSS.",
                    "example": "Log4Shell (CVE-2021-44228) has CVSS 10.0. Most real-world critical CVEs are 7–9.",
                    "level": "L0",
                },
            ],
        },
    ]

    for section in TERMS:
        st.markdown(f"### {section['category']}")
        for t in section["terms"]:
            level_tag = f" `{t['level']}`" if t["level"] else ""
            with st.expander(f"**{t['term']}**{level_tag}"):
                st.markdown(t["definition"])
                st.code(t["example"], language="python")
        st.divider()
