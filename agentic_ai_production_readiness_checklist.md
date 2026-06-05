# Agentic AI Production Readiness Checklist

Use this checklist to evaluate whether an agentic AI system is ready for production deployment.
Each item includes a one-line description explaining what should be verified.

Scoring suggestion:

- 0 = Not implemented
- 1 = Partially implemented
- 2 = Fully implemented

---

## 1. Problem & Scope Definition

- [ ] **Clear Problem Definition** — The system solves a clearly defined, bounded, and business-relevant task.
- [ ] **Task Decomposition** — The workflow explicitly separates deterministic logic from AI-driven reasoning.
- [ ] **Success Metrics Defined** — Accuracy, latency, cost, quality, and business KPIs are documented.
- [ ] **Latency Budgets per Agent Step** — Acceptable latency thresholds are defined per agent role, not only for the end-to-end flow.
- [ ] **Stop Conditions Defined** — The system has explicit conditions for when an agent must stop, escalate, or fail safely.

---

## 2. Agent Architecture

- [ ] **Agent Roles Defined** — Each agent has a clearly scoped responsibility such as planner, executor, critic, retriever, or router.
- [ ] **Orchestration Pattern Selected** — The workflow pattern such as ReAct, router, plan-execute, or reflection is intentionally chosen.
- [ ] **Loop Limits Defined** — Maximum iteration and recursion limits prevent infinite reasoning or delegation cycles.
- [ ] **Fallback Strategy** — Backup logic exists when an agent fails, returns invalid output, or cannot complete its task.
- [ ] **Agent Proliferation Control** — The number of agents is deliberately minimized and each agent’s existence is justified.
- [ ] **Escalation Path Defined** — The system defines when control moves from agent to fallback agent, human reviewer, or deterministic logic.

---

## 3. Guardrails & Safety

- [ ] **Input Filtering** — User input is sanitized to reduce prompt injection, malicious payloads, and unsafe requests.
- [ ] **Output Schema Validation** — AI outputs are validated against structured schemas before they are trusted or executed.
- [ ] **Prompt Immutability** — System prompts are protected from being overwritten or modified by downstream agent behavior.
- [ ] **Prompt Versioning** — All prompts are version-controlled so changes are traceable, reviewable, and reversible.
- [ ] **Iteration Limits** — Guardrails prevent agents from recursively calling themselves or other agents indefinitely.
- [ ] **Tool Access Restrictions** — Agents can only call approved tools with explicitly defined permissions.
- [ ] **Safety Policy Enforcement** — Domain-specific safety rules are enforced consistently before and after generation.
- [ ] **Action Approval Gates** — High-risk actions are blocked until required validations or approvals succeed.

---

## 4. Responsible AI

- [ ] **Bias Evaluation** — Outputs are tested for demographic, cultural, or contextual bias.
- [ ] **Sensitive Content Filtering** — Harmful, abusive, violent, or unsafe outputs are detected and filtered.
- [ ] **Privacy Controls** — PII detection, masking, redaction, and least-privilege data exposure are implemented.
- [ ] **Regulatory Compliance** — The system aligns with applicable requirements such as GDPR, CCPA, HIPAA, or sector-specific AI controls.
- [ ] **User Consent & Disclosure** — Users are informed when they are interacting with AI and how their data is used.
- [ ] **Explainability Requirement Defined** — The system defines where explanations are required for user trust, compliance, or auditability.

---

## 5. Hallucination Control

- [ ] **Grounding via RAG** — Responses are anchored to trusted knowledge sources when the task requires factual grounding.
- [ ] **Output Verification** — Validator logic or verifier agents confirm correctness before important outputs are used.
- [ ] **Confidence Signaling** — The system communicates uncertainty when confidence is low or evidence is weak.
- [ ] **Citation or Evidence Requirement** — Grounded answers include source references or evidence trails when appropriate.
- [ ] **Contradiction Detection** — The system checks for internal inconsistencies or contradictions before returning results.

---

## 6. Token Economics & Cost Control

- [ ] **Token Monitoring** — Token usage is tracked per request, per workflow, and per agent.
- [ ] **Prompt Optimization** — Prompts are reduced to the minimum useful context to control cost and latency.
- [ ] **Response Caching** — Frequently requested outputs or tool results are cached to avoid repeated LLM calls.
- [ ] **Cost Attribution per Agent/Workflow** — Spend is broken down by agent role and workflow path for optimization.
- [ ] **Context Budgeting** — Each workflow has explicit token budgets for prompts, retrieval, tool output, and memory injection.
- [ ] **Parallelism Budgeting** — Fan-out and concurrent calls are capped so cost does not explode under load.

---

## 7. Observability & Attribution

- [ ] **Prompt & Tool Logging** — Prompts, responses, and tool invocations are recorded for debugging and audit.
- [ ] **Agent Traceability** — Execution traces show which agents ran, in what order, and with what outcome.
- [ ] **System Metrics** — Latency, token usage, cost, error rate, throughput, and success rate are monitored.
- [ ] **Agent Identity Attribution** — Logs clearly identify which specific agent made each decision or action.
- [ ] **Decision Rationale Logging** — Important branches and decisions record enough reasoning context for human review.
- [ ] **Workflow Correlation IDs** — Every multi-step run has a unique ID so events can be tied together end-to-end.
- [ ] **Alerting & Dashboards** — Production alerts and dashboards exist for failures, degradations, and anomalous behavior.

---

## 8. Evaluation & Testing

- [ ] **Evaluation Dataset** — Benchmark prompts, golden sets, and realistic test cases exist to measure performance.
- [ ] **Regression Testing** — Automated tests detect behavior changes after model, prompt, or tool updates.
- [ ] **Adversarial Testing** — The system is tested against prompt injection, jailbreaks, malformed inputs, and edge cases.
- [ ] **Continuous Improvement Loop** — Production failures and feedback are fed back into evaluation and refinement cycles.
- [ ] **Offline vs Online Evaluation Split** — The team distinguishes between lab benchmarks and real-world production behavior.
- [ ] **Task-Specific Quality Metrics** — Metrics are tailored to the use case, such as faithfulness, code correctness, or routing accuracy.

---

## 9. Security

- [ ] **API Access Control** — Tool and integration access are protected by strong authentication and authorization.
- [ ] **Rate Limiting** — Usage limits prevent abuse, runaway loops, and denial-of-wallet scenarios.
- [ ] **Secret Protection** — API keys, tokens, and credentials are never exposed in prompts, logs, or outputs.
- [ ] **Sandboxed Execution** — Generated code or tool execution happens in isolated environments with strict controls.
- [ ] **Tenant Isolation** — Multi-tenant systems isolate data, memory, and tool access across customers or business units.
- [ ] **Outbound Data Controls** — Policies prevent sensitive data from being sent to unapproved external systems or models.

---

## 10. Human Oversight

- [ ] **Human Approval Steps** — Critical actions require human review before irreversible execution.
- [ ] **Override Capability** — Operators can stop, pause, or override agent decisions in real time.
- [ ] **Escalation to Human Defined** — Clear rules specify when the system must hand off to a human.
- [ ] **Operator Runbook Available** — Support teams have documented steps for triage, rollback, and recovery.

---

## 11. Multi-Agent Governance

- [ ] **Agent Trust Boundaries** — Explicit rules define which agents can call or delegate to which other agents.
- [ ] **Delegation Permissions** — Agents can only hand work to explicitly approved downstream agents.
- [ ] **Cascading Failure Protection** — Safeguards prevent one compromised or failing agent from poisoning the rest of the workflow.
- [ ] **Conflict Resolution Logic** — Defined mechanisms resolve disagreements between agents deterministically.
- [ ] **Deadlock Detection** — The system detects repeated loops or stalemates between agents and terminates safely.
- [ ] **Tie-Breaker Authority** — A lead agent, judge, or deterministic rule resolves unresolved conflicts.
- [ ] **Cross-Agent Permission Model** — Agent-to-agent communication is governed by explicit capability and data-sharing policies.

---

## 12. Context Integrity & Data Safety

- [ ] **Context Poisoning Protection** — Retrieved data is validated to reduce malicious, irrelevant, or adversarial context injection.
- [ ] **Tool Output Validation** — Outputs from APIs and tools are checked before they enter the model context.
- [ ] **Source Provenance Tracking** — Retrieved data includes origin metadata so it can be traced and audited.
- [ ] **Data Freshness Checks** — The system verifies whether retrieved information is still current enough for the task.
- [ ] **Trusted Source Hierarchy** — The system prioritizes authoritative sources over weaker or untrusted ones.
- [ ] **Staleness Handling Policy** — The workflow defines what happens when only stale, conflicting, or incomplete evidence is available.

---

## 13. Context Window Management

- [ ] **Context Overflow Strategy** — The system handles context-length limits gracefully instead of failing unpredictably.
- [ ] **Summarization Fallback** — Long histories are summarized when raw context no longer fits.
- [ ] **Truncation Policies** — Explicit rules define what gets dropped first when context must be reduced.
- [ ] **Context Handoff** — Tasks can continue across agents using summarized state without losing critical intent.
- [ ] **Priority Ordering of Context** — System instructions, fresh evidence, memory, and tool results are ranked by importance.
- [ ] **Near-Limit Detection** — The system detects when context usage is approaching limits and proactively adapts.

---

## 14. Model Governance & Drift Management

- [ ] **Model Version Pinning** — Specific model versions are locked where possible to maintain consistent behavior.
- [ ] **Drift Monitoring** — Behavioral differences are monitored after provider-side model changes or hidden updates.
- [ ] **Model Regression Testing** — Dedicated suites run whenever the model version, provider, or inference settings change.
- [ ] **Fallback Model Strategy** — A defined backup model exists for outages, degraded quality, or quota exhaustion.
- [ ] **Inference Setting Governance** — Temperature, top_p, max tokens, and similar settings are controlled and auditable.

---

## 15. State Management & Durable Execution

- [ ] **State Persistence** — Long-running workflows can resume after restarts, crashes, or infra failures.
- [ ] **Durable Execution** — Execution state is preserved across tasks spanning minutes, hours, or days.
- [ ] **Transaction Integrity** — Multi-step workflows maintain consistency when steps succeed or fail partially.
- [ ] **Compensating Actions Defined** — When rollback is impossible, compensating actions are documented and automated where feasible.
- [ ] **Checkpointing Strategy** — Complex workflows save intermediate state so recovery can resume from safe checkpoints.
- [ ] **Manual State Reconstruction** — Operators can reconstruct workflow state from logs and persisted events.

---

## 16. Multi-Modal Safety

- [ ] **Media Safety Checks** — Generated or processed images, audio, and video are scanned for unsafe content and PII.
- [ ] **Multi-Modal Grounding** — The model’s description of media is checked against the actual visual or audio content.
- [ ] **Media Provenance Checks** — The system tracks source and authenticity metadata for important media inputs.
- [ ] **Redaction in Media** — Sensitive details in images, audio, or video can be detected and masked before use.

---

## 17. Legal & IP Governance

- [ ] **Content Attribution** — Outputs can be traced back to the documents, sources, or datasets that influenced them.
- [ ] **License Filtering** — Retrieved code, data, or content is screened for incompatible licenses or usage restrictions.
- [ ] **Retention & Deletion Policy** — The system defines how long prompts, outputs, and memories are retained and when they are deleted.
- [ ] **Jurisdiction-Aware Handling** — Data handling and storage rules account for regional legal requirements when relevant.

---

## 18. Operational Safety & Reliability

- [ ] **Emergency Kill Switch** — Operators can instantly stop agent execution across the system.
- [ ] **Task Reconstruction** — Logs and traces support reconstruction of a failed long-running task.
- [ ] **Reliability SLOs Defined** — Availability, latency, error rate, and recovery targets are explicitly defined.
- [ ] **Provider Outage Handling** — The system defines behavior for model outages, quota exhaustion, and degraded third-party tools.
- [ ] **Circuit Breakers & Timeouts** — Repeated failures trigger protective stop conditions instead of uncontrolled retries.
- [ ] **Graceful Degradation** — The system can reduce capability safely rather than failing catastrophically.

---

## 19. Memory Architecture

- [ ] **Short-Term Session Memory** — The agent maintains coherent task context within the current session or run.
- [ ] **Long-Term Knowledge Memory** — Facts or preferences can be retrieved across sessions where appropriate.
- [ ] **Task & Workflow Memory** — Workflow state is tracked separately from conversation memory and long-term knowledge.
- [ ] **Memory Pruning & Tiering** — Irrelevant, low-value, or stale memories are archived, expired, or deprioritized.
- [ ] **Retrieval Relevance Scoring** — Only contextually relevant memory is injected into prompts.
- [ ] **Cross-Agent Memory Sharing Rules** — Explicit rules govern which agents can read or write shared memory.
- [ ] **Memory Write Permissions** — Only authorized agents can persist or update memory.
- [ ] **Memory Poisoning Protection** — Safeguards reduce false, manipulated, or adversarial facts entering memory.
- [ ] **Memory TTL / Retention Policy** — The system defines how long memories remain active before expiry or review.

---

## 20. Tool Integration

- [ ] **Tool Schema Definition** — All tool inputs and outputs are defined using clear, machine-checkable schemas.
- [ ] **Tool Invocation Validation** — Tool name, parameters, and argument types are validated before execution.
- [ ] **Retry Mechanisms** — Tools have controlled retry logic for transient failures.
- [ ] **Timeout Limits** — Strict timeouts prevent tools from hanging the agent loop.
- [ ] **Idempotency Strategy** — Repeated tool calls do not unintentionally duplicate side effects.
- [ ] **Destructive Action Classification** — High-risk actions such as deletes, sends, or deployments are explicitly classified and controlled.
- [ ] **Tool Version Tracking** — The system records tool versions or interface revisions that influenced a workflow run.

---

## 21. Infrastructure & Scaling

- [ ] **Concurrency & Rate Limits** — Parallel executions are capped to prevent resource exhaustion.
- [ ] **Async Execution & Queuing** — Queues or workflow engines manage long-running and bursty workloads safely.
- [ ] **Caching Layer** — Dedicated cache services store frequent tool outputs or intermediate results.
- [ ] **Autoscaling Strategy** — The platform can scale predictably for spikes without destabilizing agents.
- [ ] **Backpressure Handling** — The system slows or sheds load safely when downstream capacity is constrained.
- [ ] **Environment Parity** — Dev, test, and prod environments are aligned enough to make evaluation meaningful.

---

## 22. Reproducibility & Auditability

- [ ] **Run Reproducibility Controls** — Critical runs record model version, prompt version, settings, and dependencies so they can be reproduced.
- [ ] **Seed / Sampling Governance** — Randomness settings are controlled where deterministic behavior matters.
- [ ] **Audit Trail Completeness** — The system records enough evidence to explain who did what, when, and why.
- [ ] **Change Management Process** — Model, prompt, tool, and workflow changes go through review, testing, and approval.

---

## Final Production Readiness Test

1. **Explainability** — Can we explain what the agent did, why it did it, and which agent or tool was responsible?
2. **Economics** — Can we measure exactly how much the task cost by workflow path and agent role?
3. **Accuracy** — Can we verify whether the output is correct, grounded, and safe enough for use?
4. **Control** — Can we stop, pause, or override the system immediately if it deviates?
5. **Resilience** — Can we reconstruct state, recover from provider failures, and resume long-running tasks safely?
6. **Governance** — Can we audit model, prompt, memory, tool, and policy changes after the fact?

If the answer to any of these is **No**, the system is not production-ready.
