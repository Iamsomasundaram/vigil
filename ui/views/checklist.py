"""Production-readiness checklist page."""

import streamlit as st



def render_checklist() -> None:

    # ── Checklist data ─────────────────────────────────────────────────────────
    # Each item: name, desc (from the framework), score (0/1/2), note (Vigil-specific rationale)
    CHECKLIST = [
        {
            "id": 1, "name": "Problem & Scope Definition",
            "items": [
                {"name": "Clear Problem Definition",       "desc": "The system solves a clearly defined, bounded, and business-relevant task.",                                    "score": 2, "note": "CVE intelligence — well-bounded, operationally relevant."},
                {"name": "Task Decomposition",             "desc": "The workflow explicitly separates deterministic logic from AI-driven reasoning.",                              "score": 2, "note": "Change detection is deterministic code; LLM handles phrasing and analysis."},
                {"name": "Success Metrics Defined",        "desc": "Accuracy, latency, cost, quality, and business KPIs are documented.",                                         "score": 0, "note": "elapsed_ms tracked but no formal KPIs defined."},
                {"name": "Latency Budgets per Agent Step", "desc": "Acceptable latency thresholds are defined per agent role, not only end-to-end.",                              "score": 0, "note": "No per-step latency budgets defined."},
                {"name": "Stop Conditions Defined",        "desc": "The system has explicit conditions for when an agent must stop, escalate, or fail safely.",                   "score": 1, "note": "max_iterations=10 in L4; kill switch in L6. No formal escalation threshold."},
            ],
        },
        {
            "id": 2, "name": "Agent Architecture",
            "items": [
                {"name": "Agent Roles Defined",            "desc": "Each agent has a clearly scoped responsibility: planner, executor, critic, retriever, or router.",            "score": 2, "note": "Each level and L2 sub-agent has a single explicit responsibility."},
                {"name": "Orchestration Pattern Selected", "desc": "The workflow pattern (ReAct, router, plan-execute, reflection) is intentionally chosen.",                     "score": 2, "note": "ReAct (L4), router (L3), parallel fan-out (L2), monitor loop (L6) — all explicit."},
                {"name": "Loop Limits Defined",            "desc": "Maximum iteration and recursion limits prevent infinite reasoning or delegation cycles.",                      "score": 2, "note": "max_iterations=10 in L4 tool loop, documented in code."},
                {"name": "Fallback Strategy",              "desc": "Backup logic exists when an agent fails, returns invalid output, or cannot complete its task.",               "score": 1, "note": "Broad except blocks prevent crashes; no structured fallback path."},
                {"name": "Agent Proliferation Control",    "desc": "The number of agents is deliberately minimized and each agent's existence is justified.",                     "score": 2, "note": "Exactly the agents needed per level — no speculative extras."},
                {"name": "Escalation Path Defined",        "desc": "The system defines when control moves from agent to fallback, human reviewer, or deterministic logic.",       "score": 1, "note": "needs_human_review track exists in L3; no automated escalation trigger."},
            ],
        },
        {
            "id": 3, "name": "Guardrails & Safety",
            "items": [
                {"name": "Input Filtering",                "desc": "User input is sanitized to reduce prompt injection, malicious payloads, and unsafe requests.",               "score": 0, "note": "CVE IDs passed directly to prompts — no validation or sanitization."},
                {"name": "Output Schema Validation",       "desc": "AI outputs are validated against structured schemas before they are trusted or executed.",                    "score": 2, "note": "Pydantic strict mode + strict=True JSON schema enforced on all structured calls."},
                {"name": "Prompt Immutability",            "desc": "System prompts are protected from being overwritten or modified by downstream agent behavior.",               "score": 1, "note": "Prompts are in code (not DB-editable) but no explicit runtime protection."},
                {"name": "Prompt Versioning",              "desc": "All prompts are version-controlled so changes are traceable, reviewable, and reversible.",                    "score": 1, "note": "Prompts are in git but no semantic versioning or change log."},
                {"name": "Iteration Limits",               "desc": "Guardrails prevent agents from recursively calling themselves or other agents indefinitely.",                 "score": 2, "note": "max_iterations=10 with explicit safety comment in L4."},
                {"name": "Tool Access Restrictions",       "desc": "Agents can only call approved tools with explicitly defined permissions.",                                    "score": 1, "note": "Only two tools defined (NVD, EPSS); no permission model enforced at runtime."},
                {"name": "Safety Policy Enforcement",      "desc": "Domain-specific safety rules are enforced consistently before and after generation.",                         "score": 0, "note": "No domain safety rules enforced programmatically."},
                {"name": "Action Approval Gates",          "desc": "High-risk actions are blocked until required validations or approvals succeed.",                              "score": 0, "note": "Alerts are generated and stored automatically with no approval step."},
            ],
        },
        {
            "id": 4, "name": "Responsible AI",
            "items": [
                {"name": "Bias Evaluation",                "desc": "Outputs are tested for demographic, cultural, or contextual bias.",                                           "score": 0, "note": "Not evaluated — low risk for CVE scoring but not assessed."},
                {"name": "Sensitive Content Filtering",    "desc": "Harmful, abusive, violent, or unsafe outputs are detected and filtered.",                                    "score": 0, "note": "Not implemented — not the primary concern for a CVE tool."},
                {"name": "Privacy Controls",               "desc": "PII detection, masking, redaction, and least-privilege data exposure are implemented.",                      "score": 0, "note": "CVE IDs are public data; no PII controls exist."},
                {"name": "Regulatory Compliance",          "desc": "The system aligns with GDPR, CCPA, HIPAA, or sector-specific AI controls.",                                  "score": 0, "note": "Not assessed."},
                {"name": "User Consent & Disclosure",      "desc": "Users are informed when interacting with AI and how their data is used.",                                    "score": 0, "note": "No disclosure UI."},
                {"name": "Explainability Defined",         "desc": "The system defines where explanations are required for trust, compliance, or auditability.",                 "score": 1, "note": "Reasoning included in outputs; no formal explainability requirement documented."},
            ],
        },
        {
            "id": 5, "name": "Hallucination Control",
            "items": [
                {"name": "Grounding via Live APIs",        "desc": "Responses are anchored to trusted knowledge sources when the task requires factual grounding.",               "score": 2, "note": "All scores come from live NVD + EPSS API calls — not model training memory."},
                {"name": "Output Verification",            "desc": "Validator logic or verifier agents confirm correctness before important outputs are used.",                   "score": 1, "note": "Schema validation catches format errors; no semantic correctness check."},
                {"name": "Confidence Signaling",           "desc": "The system communicates uncertainty when confidence is low or evidence is weak.",                             "score": 0, "note": "No confidence scores or uncertainty markers in outputs."},
                {"name": "Citation or Evidence",           "desc": "Grounded answers include source references or evidence trails when appropriate.",                             "score": 1, "note": "data_sources field in L4/L5 output; not enforced on all levels."},
                {"name": "Contradiction Detection",        "desc": "The system checks for internal inconsistencies or contradictions before returning results.",                  "score": 0, "note": "Not implemented."},
            ],
        },
        {
            "id": 6, "name": "Token Economics & Cost Control",
            "items": [
                {"name": "Token Monitoring",               "desc": "Token usage is tracked per request, per workflow, and per agent.",                                            "score": 1, "note": "Estimated token counts and cost tracked per level run via get_usage(); shown in UI after each run."},
                {"name": "Prompt Optimization",            "desc": "Prompts are reduced to the minimum useful context to control cost and latency.",                              "score": 1, "note": "Prompts are focused per level but not formally optimized."},
                {"name": "Response Caching",               "desc": "Frequently requested outputs or tool results are cached to avoid repeated LLM calls.",                       "score": 0, "note": "No caching — repeated CVE scans always call the LLM."},
                {"name": "Cost Attribution",               "desc": "Spend is broken down by agent role and workflow path for optimization.",                                      "score": 1, "note": "Per-level cost shown in UI after each run (gpt-4o-mini pricing); no per-agent-role breakdown yet."},
                {"name": "Context Budgeting",              "desc": "Each workflow has explicit token budgets for prompts, retrieval, tool output, and memory.",                   "score": 0, "note": "max_tokens set per call but no budget policy across the workflow."},
                {"name": "Parallelism Budgeting",          "desc": "Fan-out and concurrent calls are capped so cost does not explode under load.",                               "score": 2, "note": "asyncio.Semaphore(5) caps concurrent NVD/EPSS calls in L6."},
            ],
        },
        {
            "id": 7, "name": "Observability & Attribution",
            "items": [
                {"name": "Prompt & Tool Logging",          "desc": "Prompts, responses, and tool invocations are recorded for debugging and audit.",                              "score": 1, "note": "tool_log saved to DB in L4/L5; rich console logging. No structured log sink."},
                {"name": "Agent Traceability",             "desc": "Execution traces show which agents ran, in what order, and with what outcome.",                               "score": 1, "note": "Tool call sequence visible in L4/L5 response; no end-to-end trace IDs."},
                {"name": "System Metrics",                 "desc": "Latency, token usage, cost, error rate, throughput, and success rate are monitored.",                        "score": 1, "note": "elapsed_ms + total_tokens + cost tracked per request; no error-rate or throughput metrics."},
                {"name": "Agent Identity Attribution",     "desc": "Logs clearly identify which specific agent made each decision or action.",                                    "score": 1, "note": "L2 labels per-agent reports; L6 alert has auto_generated=True."},
                {"name": "Decision Rationale Logging",     "desc": "Important branches and decisions record enough context for human review.",                                    "score": 1, "note": "Routing decisions include reason field; L6 change_type explains alert trigger."},
                {"name": "Workflow Correlation IDs",       "desc": "Every multi-step run has a unique ID so events can be tied together end-to-end.",                            "score": 0, "note": "No correlation IDs — runs cannot be linked across steps."},
                {"name": "Alerting & Dashboards",          "desc": "Production alerts and dashboards exist for failures, degradations, and anomalous behavior.",                 "score": 1, "note": "L6 alerts table covers domain alerts; no infrastructure monitoring."},
            ],
        },
        {
            "id": 8, "name": "Evaluation & Testing",
            "items": [
                {"name": "Evaluation Dataset",             "desc": "Benchmark prompts, golden sets, and realistic test cases exist to measure performance.",                      "score": 0, "note": "3 suggested CVEs in the README — not a formal benchmark."},
                {"name": "Regression Testing",             "desc": "Automated tests detect behavior changes after model, prompt, or tool updates.",                               "score": 1, "note": "tests/test_l6_scan.py covers empty watchlist key, multi-CVE parallel scan, and monitor lifecycle."},
                {"name": "Adversarial Testing",            "desc": "The system is tested against prompt injection, jailbreaks, malformed inputs, and edge cases.",               "score": 0, "note": "Not tested."},
                {"name": "Continuous Improvement Loop",    "desc": "Production failures and feedback are fed back into evaluation and refinement cycles.",                        "score": 1, "note": "L5 feedback mechanism (patched/dismissed/etc.) creates a feedback signal."},
                {"name": "Offline vs Online Eval Split",   "desc": "The team distinguishes between lab benchmarks and real-world production behavior.",                           "score": 0, "note": "Not defined."},
                {"name": "Task-Specific Quality Metrics",  "desc": "Metrics are tailored to the use case: faithfulness, routing accuracy, etc.",                                 "score": 0, "note": "No task-specific metrics defined."},
            ],
        },
        {
            "id": 9, "name": "Security",
            "items": [
                {"name": "API Access Control",             "desc": "Tool and integration access are protected by strong authentication and authorization.",                       "score": 0, "note": "FastAPI has no authentication — all endpoints are open."},
                {"name": "Rate Limiting",                  "desc": "Usage limits prevent abuse, runaway loops, and denial-of-wallet scenarios.",                                 "score": 0, "note": "No rate limiting on any endpoint."},
                {"name": "Secret Protection",              "desc": "API keys, tokens, and credentials are never exposed in prompts, logs, or outputs.",                          "score": 2, "note": "OPENAI_API_KEY via env var; .env.example pattern; .gitignore covers .env."},
                {"name": "Sandboxed Execution",            "desc": "Generated code or tool execution happens in isolated environments with strict controls.",                    "score": 1, "note": "Docker container provides OS-level isolation; no code execution in the project."},
                {"name": "Tenant Isolation",               "desc": "Multi-tenant systems isolate data, memory, and tool access across customers or business units.",             "score": 0, "note": "Single-tenant learning project."},
                {"name": "Outbound Data Controls",         "desc": "Policies prevent sensitive data from being sent to unapproved external systems or models.",                  "score": 0, "note": "CVE IDs sent to OpenAI with no data classification policy."},
            ],
        },
        {
            "id": 10, "name": "Human Oversight",
            "items": [
                {"name": "Human Approval Steps",           "desc": "Critical actions require human review before irreversible execution.",                                        "score": 0, "note": "Alerts are generated without human approval."},
                {"name": "Override Capability",            "desc": "Operators can stop, pause, or override agent decisions in real time.",                                        "score": 2, "note": "POST /l6/monitor/stop cancels the background task immediately."},
                {"name": "Escalation to Human Defined",   "desc": "Clear rules specify when the system must hand off to a human.",                                               "score": 1, "note": "needs_human_review routing track exists; no automated handoff mechanism."},
                {"name": "Operator Runbook Available",     "desc": "Support teams have documented steps for triage, rollback, and recovery.",                                    "score": 0, "note": "README covers setup only — no incident response playbook."},
            ],
        },
        {
            "id": 11, "name": "Multi-Agent Governance",
            "items": [
                {"name": "Agent Trust Boundaries",         "desc": "Explicit rules define which agents can call or delegate to which other agents.",                              "score": 1, "note": "Implicit in code structure (dispatch table); not enforced at runtime."},
                {"name": "Delegation Permissions",         "desc": "Agents can only hand work to explicitly approved downstream agents.",                                         "score": 1, "note": "TRACK_HANDLERS dict is an explicit allowlist for L3 delegation."},
                {"name": "Cascading Failure Protection",   "desc": "Safeguards prevent one failing agent from poisoning the rest of the workflow.",                               "score": 1, "note": "return_exceptions=True in asyncio.gather() — one failure doesn't abort the scan."},
                {"name": "Conflict Resolution Logic",      "desc": "Defined mechanisms resolve disagreements between agents deterministically.",                                  "score": 1, "note": "L2 moderator agent synthesises conflicting reports into a verdict."},
                {"name": "Deadlock Detection",             "desc": "The system detects repeated loops or stalemates between agents and terminates safely.",                      "score": 1, "note": "max_iterations=10 prevents infinite tool loops; no cross-agent deadlock detection."},
                {"name": "Tie-Breaker Authority",          "desc": "A lead agent, judge, or deterministic rule resolves unresolved conflicts.",                                  "score": 1, "note": "L2 moderator acts as tie-breaker; L3 router decision is deterministic."},
                {"name": "Cross-Agent Permission Model",   "desc": "Agent-to-agent communication is governed by explicit capability and data-sharing policies.",                 "score": 0, "note": "No formal permission model between agents."},
            ],
        },
        {
            "id": 12, "name": "Context Integrity & Data Safety",
            "items": [
                {"name": "Context Poisoning Protection",   "desc": "Retrieved data is validated to reduce malicious or adversarial context injection.",                          "score": 0, "note": "NVD/EPSS responses injected into prompts without sanitization."},
                {"name": "Tool Output Validation",         "desc": "Outputs from APIs and tools are checked before they enter the model context.",                               "score": 1, "note": "Pydantic validates final structured output; raw tool responses are not pre-checked."},
                {"name": "Source Provenance Tracking",     "desc": "Retrieved data includes origin metadata so it can be traced and audited.",                                   "score": 1, "note": "data_sources field in L4/L5 output names NVD and EPSS."},
                {"name": "Data Freshness Checks",          "desc": "The system verifies whether retrieved information is still current enough for the task.",                    "score": 0, "note": "No freshness checks — assumes NVD/EPSS data is current."},
                {"name": "Trusted Source Hierarchy",       "desc": "The system prioritizes authoritative sources over weaker or untrusted ones.",                                "score": 1, "note": "NVD and EPSS are authoritative; no fallback to weaker sources."},
                {"name": "Staleness Handling Policy",      "desc": "The workflow defines what happens when only stale or incomplete evidence is available.",                      "score": 0, "note": "NVD API failures return 0.0 defaults silently — no explicit policy."},
            ],
        },
        {
            "id": 13, "name": "Context Window Management",
            "items": [
                {"name": "Context Overflow Strategy",      "desc": "The system handles context-length limits gracefully instead of failing unpredictably.",                      "score": 0, "note": "No overflow strategy — long histories could exceed context limits."},
                {"name": "Summarization Fallback",         "desc": "Long histories are summarized when raw context no longer fits.",                                              "score": 0, "note": "L5 injects full history as text — no summarization for long histories."},
                {"name": "Truncation Policies",            "desc": "Explicit rules define what gets dropped first when context must be reduced.",                                "score": 0, "note": "Not defined."},
                {"name": "Context Handoff",                "desc": "Tasks can continue across agents using summarized state without losing critical intent.",                    "score": 0, "note": "Not implemented for multi-session continuity."},
                {"name": "Priority Ordering of Context",   "desc": "System instructions, fresh evidence, memory, and tool results are ranked by importance.",                   "score": 1, "note": "System prompt → memory context → live tool results ordering is implicit."},
                {"name": "Near-Limit Detection",           "desc": "The system detects when context usage is approaching limits and proactively adapts.",                       "score": 0, "note": "Not implemented."},
            ],
        },
        {
            "id": 14, "name": "Model Governance & Drift Management",
            "items": [
                {"name": "Model Version Pinning",          "desc": "Specific model versions are locked where possible to maintain consistent behavior.",                         "score": 1, "note": "OPENAI_MODEL env var defaults to gpt-4o-mini; not pinned to a specific snapshot."},
                {"name": "Drift Monitoring",               "desc": "Behavioral differences are monitored after provider-side model changes or hidden updates.",                  "score": 0, "note": "Not monitored."},
                {"name": "Model Regression Testing",       "desc": "Dedicated test suites run whenever the model version, provider, or settings change.",                       "score": 0, "note": "No test suite."},
                {"name": "Fallback Model Strategy",        "desc": "A defined backup model exists for outages, degraded quality, or quota exhaustion.",                         "score": 0, "note": "No fallback model defined."},
                {"name": "Inference Setting Governance",   "desc": "Temperature, top_p, max_tokens, and similar settings are controlled and auditable.",                        "score": 1, "note": "temperature and max_tokens set explicitly per call; not centrally governed."},
            ],
        },
        {
            "id": 15, "name": "State Management & Durable Execution",
            "items": [
                {"name": "State Persistence",              "desc": "Long-running workflows can resume after restarts, crashes, or infra failures.",                              "score": 2, "note": "PostgreSQL persists scan_state, analyses, alerts, watchlist across restarts."},
                {"name": "Durable Execution",              "desc": "Execution state is preserved across tasks spanning minutes, hours, or days.",                                "score": 1, "note": "DB state survives restarts; in-flight monitor loop restarts from scratch."},
                {"name": "Transaction Integrity",          "desc": "Multi-step workflows maintain consistency when steps succeed or fail partially.",                            "score": 0, "note": "No DB transactions wrapping multi-step writes."},
                {"name": "Compensating Actions Defined",   "desc": "When rollback is impossible, compensating actions are documented and automated where feasible.",             "score": 0, "note": "Not defined."},
                {"name": "Checkpointing Strategy",         "desc": "Complex workflows save intermediate state so recovery can resume from safe checkpoints.",                   "score": 0, "note": "Not implemented."},
                {"name": "Manual State Reconstruction",    "desc": "Operators can reconstruct workflow state from logs and persisted events.",                                   "score": 1, "note": "DB tables are human-queryable; no reconstruction playbook."},
            ],
        },
        {
            "id": 16, "name": "Multi-Modal Safety",
            "items": [
                {"name": "Media Safety Checks",            "desc": "Generated or processed images, audio, and video are scanned for unsafe content and PII.",                   "score": 0, "note": "N/A — text-only system."},
                {"name": "Multi-Modal Grounding",          "desc": "The model's description of media is checked against the actual visual or audio content.",                   "score": 0, "note": "N/A — text-only system."},
                {"name": "Media Provenance Checks",        "desc": "The system tracks source and authenticity metadata for important media inputs.",                             "score": 0, "note": "N/A — text-only system."},
                {"name": "Redaction in Media",             "desc": "Sensitive details in images, audio, or video can be detected and masked before use.",                       "score": 0, "note": "N/A — text-only system."},
            ],
        },
        {
            "id": 17, "name": "Legal & IP Governance",
            "items": [
                {"name": "Content Attribution",            "desc": "Outputs can be traced back to the documents, sources, or datasets that influenced them.",                    "score": 1, "note": "data_sources field names NVD and EPSS in L4/L5."},
                {"name": "License Filtering",              "desc": "Retrieved code, data, or content is screened for incompatible licenses or usage restrictions.",              "score": 0, "note": "NVD data is public domain; not formally assessed."},
                {"name": "Retention & Deletion Policy",    "desc": "The system defines how long prompts, outputs, and memories are retained and when deleted.",                  "score": 0, "note": "Data retained indefinitely in PostgreSQL — no TTL or deletion policy."},
                {"name": "Jurisdiction-Aware Handling",    "desc": "Data handling and storage rules account for regional legal requirements when relevant.",                     "score": 0, "note": "Not assessed."},
            ],
        },
        {
            "id": 18, "name": "Operational Safety & Reliability",
            "items": [
                {"name": "Emergency Kill Switch",          "desc": "Operators can instantly stop agent execution across the system.",                                             "score": 2, "note": "POST /l6/monitor/stop cancels the background task immediately."},
                {"name": "Task Reconstruction",            "desc": "Logs and traces support reconstruction of a failed long-running task.",                                      "score": 1, "note": "DB tables allow partial reconstruction; no structured incident log."},
                {"name": "Reliability SLOs Defined",       "desc": "Availability, latency, error rate, and recovery targets are explicitly defined.",                           "score": 0, "note": "Not defined."},
                {"name": "Provider Outage Handling",       "desc": "The system defines behavior for model outages, quota exhaustion, and degraded third-party tools.",          "score": 1, "note": "OpenAI timeout=60s; NVD/EPSS failures return safe defaults. No quota handling."},
                {"name": "Circuit Breakers & Timeouts",    "desc": "Repeated failures trigger protective stop conditions instead of uncontrolled retries.",                     "score": 1, "note": "Timeouts set; no circuit-breaker pattern for sustained failures."},
                {"name": "Graceful Degradation",           "desc": "The system can reduce capability safely rather than failing catastrophically.",                              "score": 1, "note": "return_exceptions=True allows partial scan completion; no degraded-mode logic."},
            ],
        },
        {
            "id": 19, "name": "Memory Architecture",
            "items": [
                {"name": "Short-Term Session Memory",      "desc": "The agent maintains coherent task context within the current session or run.",                               "score": 2, "note": "messages list in L4/L5 maintains full conversation context within a run."},
                {"name": "Long-Term Knowledge Memory",     "desc": "Facts or preferences can be retrieved across sessions where appropriate.",                                   "score": 2, "note": "PostgreSQL analyses table persists history across restarts."},
                {"name": "Task & Workflow Memory",         "desc": "Workflow state is tracked separately from conversation memory and long-term knowledge.",                     "score": 1, "note": "scan_state and tool_log stored; not formally separated from analysis memory."},
                {"name": "Memory Pruning & Tiering",       "desc": "Irrelevant, low-value, or stale memories are archived, expired, or deprioritized.",                        "score": 0, "note": "All history retained forever — no pruning or tiering."},
                {"name": "Retrieval Relevance Scoring",    "desc": "Only contextually relevant memory is injected into prompts.",                                                "score": 0, "note": "All history injected — no relevance scoring or filtering."},
                {"name": "Cross-Agent Memory Sharing",     "desc": "Explicit rules govern which agents can read or write shared memory.",                                        "score": 0, "note": "All agents share one DB schema with no access rules."},
                {"name": "Memory Write Permissions",       "desc": "Only authorized agents can persist or update memory.",                                                       "score": 0, "note": "No write permission controls."},
                {"name": "Memory Poisoning Protection",    "desc": "Safeguards reduce false, manipulated, or adversarial facts entering memory.",                               "score": 0, "note": "Not implemented."},
                {"name": "Memory TTL / Retention Policy",  "desc": "The system defines how long memories remain active before expiry or review.",                               "score": 0, "note": "No TTL — memories are permanent until manually deleted."},
            ],
        },
        {
            "id": 20, "name": "Tool Integration",
            "items": [
                {"name": "Tool Schema Definition",         "desc": "All tool inputs and outputs are defined using clear, machine-checkable schemas.",                            "score": 2, "note": "OpenAI function schemas defined explicitly in TOOLS list in L4."},
                {"name": "Tool Invocation Validation",     "desc": "Tool name, parameters, and argument types are validated before execution.",                                  "score": 1, "note": "OpenAI validates tool call structure; no additional pre-execution check."},
                {"name": "Retry Mechanisms",               "desc": "Tools have controlled retry logic for transient failures.",                                                  "score": 0, "note": "No retry logic — failures return defaults or propagate as exceptions."},
                {"name": "Timeout Limits",                 "desc": "Strict timeouts prevent tools from hanging the agent loop.",                                                 "score": 2, "note": "OpenAI timeout=60s; httpx async client has default timeouts set."},
                {"name": "Idempotency Strategy",           "desc": "Repeated tool calls do not unintentionally duplicate side effects.",                                        "score": 1, "note": "NVD/EPSS are read-only (naturally idempotent); not explicitly designed."},
                {"name": "Destructive Action Classification","desc":"High-risk actions (deletes, sends, deployments) are explicitly classified and controlled.",                "score": 0, "note": "No classification — all tools are read-only, so risk is low."},
                {"name": "Tool Version Tracking",          "desc": "The system records tool versions or interface revisions that influenced a workflow run.",                    "score": 0, "note": "NVD API version not recorded in outputs."},
            ],
        },
        {
            "id": 21, "name": "Infrastructure & Scaling",
            "items": [
                {"name": "Concurrency & Rate Limits",      "desc": "Parallel executions are capped to prevent resource exhaustion.",                                             "score": 2, "note": "asyncio.Semaphore(5) caps concurrent scans in L6."},
                {"name": "Async Execution & Queuing",      "desc": "Queues or workflow engines manage long-running and bursty workloads safely.",                               "score": 2, "note": "asyncio throughout; background task managed by asyncio.Task."},
                {"name": "Caching Layer",                  "desc": "Dedicated cache services store frequent tool outputs or intermediate results.",                              "score": 0, "note": "Redis is in the stack but not used for caching yet."},
                {"name": "Autoscaling Strategy",           "desc": "The platform can scale predictably for spikes without destabilizing agents.",                               "score": 0, "note": "Single Docker container — no autoscaling."},
                {"name": "Backpressure Handling",          "desc": "The system slows or sheds load safely when downstream capacity is constrained.",                            "score": 1, "note": "Semaphore provides natural backpressure on concurrent scans."},
                {"name": "Environment Parity",             "desc": "Dev, test, and prod environments are aligned enough to make evaluation meaningful.",                         "score": 1, "note": "Docker Compose provides consistent environments; no separate prod config."},
            ],
        },
        {
            "id": 22, "name": "Reproducibility & Auditability",
            "items": [
                {"name": "Run Reproducibility Controls",   "desc": "Critical runs record model version, prompt version, settings, and dependencies.",                           "score": 0, "note": "Model version not recorded per-run; prompt version not tracked."},
                {"name": "Seed / Sampling Governance",     "desc": "Randomness settings are controlled where deterministic behavior matters.",                                   "score": 1, "note": "temperature set explicitly (0.1–0.2); no seed pinning."},
                {"name": "Audit Trail Completeness",       "desc": "The system records enough evidence to explain who did what, when, and why.",                                 "score": 1, "note": "DB stores analyses, feedback, alerts with timestamps. No user identity tracking."},
                {"name": "Change Management Process",      "desc": "Model, prompt, tool, and workflow changes go through review, testing, and approval.",                       "score": 0, "note": "Git history exists but no formal review/approval process."},
            ],
        },
    ]

    # ── Aggregate scores ────────────────────────────────────────────────────────
    all_items    = [item for cat in CHECKLIST for item in cat["items"]]
    total_score  = sum(i["score"] for i in all_items)
    max_score    = len(all_items) * 2
    pct          = total_score / max_score * 100
    n_full       = sum(1 for i in all_items if i["score"] == 2)
    n_partial    = sum(1 for i in all_items if i["score"] == 1)
    n_none       = sum(1 for i in all_items if i["score"] == 0)

    def score_badge(score: int) -> str:
        if score == 2:
            return '<span style="background:#21C354;color:white;padding:1px 8px;border-radius:10px;font-size:0.8em;font-weight:bold">✓ Full</span>'
        if score == 1:
            return '<span style="background:#FFA500;color:white;padding:1px 8px;border-radius:10px;font-size:0.8em;font-weight:bold">~ Partial</span>'
        return '<span style="background:#FF4B4B;color:white;padding:1px 8px;border-radius:10px;font-size:0.8em;font-weight:bold">✗ Gap</span>'

    def cat_colour(score_pct: float) -> str:
        if score_pct >= 70:  return "#21C354"
        if score_pct >= 35:  return "#FFA500"
        return "#FF4B4B"

    # ── Page header ─────────────────────────────────────────────────────────────
    st.title("📋 Production Readiness Checklist")
    st.caption(
        "Vigil scored against the **Agentic AI Production Readiness** framework — "
        "22 categories · 134 items · 0 = not implemented · 1 = partial · 2 = fully implemented"
    )

    # Overall score bar
    bar_colour = cat_colour(pct)
    st.markdown(
        f"""
        <div style="background:#1E1E2E;padding:16px 20px;border-radius:8px;margin-bottom:8px">
          <div style="display:flex;justify-content:space-between;margin-bottom:6px">
            <span style="color:#E2E8F0;font-weight:bold;font-size:1.1em">Overall Score</span>
            <span style="color:{bar_colour};font-weight:bold;font-size:1.3em">{total_score} / {max_score} &nbsp;·&nbsp; {pct:.0f}%</span>
          </div>
          <div style="background:#2D2D3F;border-radius:6px;height:14px;overflow:hidden">
            <div style="background:{bar_colour};width:{pct:.1f}%;height:100%;border-radius:6px"></div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Items",        len(all_items))
    c2.metric("✅ Fully Implemented", n_full,    delta=f"{n_full/len(all_items)*100:.0f}% of items")
    c3.metric("🟡 Partial",          n_partial,  delta=f"{n_partial/len(all_items)*100:.0f}% of items")
    c4.metric("🔴 Gaps",             n_none,     delta=f"{n_none/len(all_items)*100:.0f}% of items",  delta_color="inverse")

    st.divider()

    # ── Category summary grid ───────────────────────────────────────────────────
    st.markdown("### Category Overview")
    st.caption("Colour = score % for that category.  🟢 ≥70%  ·  🟡 35–70%  ·  🔴 <35%")

    cols = st.columns(4)
    for idx, cat in enumerate(CHECKLIST):
        cat_total = sum(i["score"] for i in cat["items"])
        cat_max   = len(cat["items"]) * 2
        cat_pct   = cat_total / cat_max * 100
        colour    = cat_colour(cat_pct)
        with cols[idx % 4]:
            # Wrap in <a> pointing to the anchor placed just above that category's expander.
            # cursor:pointer + subtle opacity shift on hover give a clickable affordance.
            st.markdown(
                f"""
                <a href="#cat-{cat['id']}" style="text-decoration:none;display:block">
                  <div style="background:#1E1E2E;border-left:4px solid {colour};
                              padding:10px 12px;border-radius:6px;margin-bottom:10px;
                              cursor:pointer;transition:opacity 0.15s"
                       onmouseover="this.style.opacity='0.7'"
                       onmouseout="this.style.opacity='1'">
                    <div style="color:#94A3B8;font-size:0.75em">§{cat['id']}</div>
                    <div style="color:#E2E8F0;font-size:0.85em;font-weight:600;line-height:1.3">{cat['name']}</div>
                    <div style="color:{colour};font-weight:bold;font-size:1em;margin-top:4px">
                      {cat_total}/{cat_max} &nbsp;<span style="font-size:0.8em;font-weight:normal">({cat_pct:.0f}%)</span>
                    </div>
                  </div>
                </a>
                """,
                unsafe_allow_html=True,
            )

    st.divider()

    # ── Filter ──────────────────────────────────────────────────────────────────
    st.markdown("### Detailed Checklist")
    filter_choice = st.radio(
        "Show",
        ["All items", "🔴 Gaps only", "🟡 Partial only", "✅ Fully implemented"],
        horizontal=True,
        key="cl_filter",
    )
    filter_map = {
        "All items":             {0, 1, 2},
        "🔴 Gaps only":         {0},
        "🟡 Partial only":      {1},
        "✅ Fully implemented":  {2},
    }
    visible_scores = filter_map[filter_choice]

    # ── Per-category expanders ──────────────────────────────────────────────────
    for cat in CHECKLIST:
        visible = [i for i in cat["items"] if i["score"] in visible_scores]
        if not visible:
            continue  # skip category entirely if filter hides all its items

        cat_total = sum(i["score"] for i in cat["items"])
        cat_max   = len(cat["items"]) * 2
        cat_pct   = cat_total / cat_max * 100
        colour    = cat_colour(cat_pct)

        # Anchor target — the card's href="#cat-N" lands here
        st.markdown(f'<div id="cat-{cat["id"]}"></div>', unsafe_allow_html=True)
        with st.expander(
            f"§{cat['id']}  {cat['name']}  —  {cat_total}/{cat_max} ({cat_pct:.0f}%)",
            expanded=False,
        ):
            # Category progress bar
            st.markdown(
                f'<div style="background:#2D2D3F;border-radius:4px;height:6px;margin-bottom:14px">'
                f'<div style="background:{colour};width:{cat_pct:.1f}%;height:100%;border-radius:4px"></div>'
                f'</div>',
                unsafe_allow_html=True,
            )

            # Item rows
            rows_html = ""
            for item in visible:
                badge_html = score_badge(item["score"])
                rows_html += (
                    f'<div style="display:flex;align-items:flex-start;gap:10px;'
                    f'padding:8px 0;border-bottom:1px solid #2D2D3F">'
                    f'<div style="min-width:80px;padding-top:1px">{badge_html}</div>'
                    f'<div>'
                    f'<div style="color:#E2E8F0;font-weight:600;font-size:0.9em">{item["name"]}</div>'
                    f'<div style="color:#94A3B8;font-size:0.8em;margin-top:2px">{item["desc"]}</div>'
                    f'<div style="color:#7C9CBF;font-size:0.8em;margin-top:3px;font-style:italic">▸ Vigil: {item["note"]}</div>'
                    f'</div></div>'
                )

            st.markdown(
                f'<div style="background:#1E1E2E;padding:4px 12px;border-radius:6px">{rows_html}</div>',
                unsafe_allow_html=True,
            )

    # ── Final 6 questions ───────────────────────────────────────────────────────
    st.divider()
    st.markdown("### Final Production Readiness Test")
    st.caption("From the framework: if any answer is **No**, the system is not production-ready.")

    final_six = [
        ("Explainability", "Can we explain what the agent did, why it did it, and which agent or tool was responsible?",        "🟡", "Partial — tool log and routing reason visible; no end-to-end trace IDs."),
        ("Economics",      "Can we measure exactly how much the task cost by workflow path and agent role?",                    "🟡", "Partial — per-level token count and cost now tracked; no per-agent-role breakdown yet."),
        ("Accuracy",       "Can we verify whether the output is correct, grounded, and safe enough for use?",                  "🟡", "Partial — grounded in NVD/EPSS; no automated correctness verification."),
        ("Control",        "Can we stop, pause, or override the system immediately if it deviates?",                           "🟢", "Yes — L6 kill switch stops the monitor in milliseconds."),
        ("Resilience",     "Can we reconstruct state, recover from provider failures, and resume long-running tasks safely?",  "🟡", "Partial — DB state survives restarts; no checkpoint/resume for in-flight tasks."),
        ("Governance",     "Can we audit model, prompt, memory, tool, and policy changes after the fact?",                     "🔴", "No — git history exists but no formal audit trail for prompt or model changes."),
    ]

    for label, question, status, verdict in final_six:
        status_colour = {"🟢": "#21C354", "🟡": "#FFA500", "🔴": "#FF4B4B"}[status]
        st.markdown(
            f"""
            <div style="display:flex;align-items:flex-start;gap:14px;
                        padding:10px 14px;margin-bottom:8px;border-radius:6px;
                        background:#1E1E2E;border-left:4px solid {status_colour}">
              <div style="font-size:1.4em;min-width:28px">{status}</div>
              <div>
                <div style="color:#E2E8F0;font-weight:bold">{label}</div>
                <div style="color:#94A3B8;font-size:0.85em;margin-top:2px">{question}</div>
                <div style="color:{status_colour};font-size:0.85em;margin-top:4px">{verdict}</div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
