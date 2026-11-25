---
title: Reliability overview
summary: Why an agent that works in a demo is not yet an agent you can trust, and the nine layers Vigil adds.
section: Reliability
order: 1
---

# Reliability: from "it works" to "I can trust it"

**The question this track answers:** the agent worked when I tried it. Why would I let it act on real systems?

A demo only proves that one run went well. Real use brings runs you never tried: poisoned input, a data source that is down, a prompt change that quietly makes answers worse, a bill that doubles. This track adds the layers that turn a clever demo into something you can depend on.

## Why agents need more than a good prompt

A normal program fails in ways you can predict and test. An agent adds three new problems:

- **It reads untrusted text and may obey it.** A CVE description is written by outsiders. If it says "ignore your instructions", a naive agent may comply.
- **Its output is not deterministic.** The same input can give different answers, so "the test passed once" means little.
- **It depends on things outside your control.** The model, the NVD feed and the EPSS service can all be slow, wrong or down.

Each problem needs its own defence. That is why this track has several modules, not one.

## The trust ladder

Think of reliability as a ladder. Each rung answers one question, and you should not trust an agent more than the rungs you have built.

{{flow: R1 Guardrails ~ can it be tricked? | R2 Evaluation ~ is it good, and still good? | R3 Observability ~ what did it actually do? | R4 Resilience ~ what if a source fails? | R5 Cost control ~ can it run up a bill?}}

R1 to R5 are the foundation and each has its own page here. R6 to R9 cover running agents over time and releasing changes safely; they have their own pages.

## The nine modules at a glance

| Module | One line | Where the code lives |
| --- | --- | --- |
| [R1: Guardrails](r1.md) | Detect and contain prompt injection, restrict tools, and enforce policy on the model's answer | `reliability/r1_guardrails.py` |
| [R2: Evaluation](r2.md) | Score the agent on a fixed set of cases and fail a change that makes it worse | `reliability/r2_evaluation.py` |
| [R3: Observability](r3.md) | Record a tree of timed steps for each run so you can see what happened | `reliability/r3_observability.py` |
| [R4: Resilience](r4.md) | Retry, time out, break circuits and degrade gracefully when a source fails | `reliability/r4_resilience.py` |
| [R5: Cost control](r5.md) | Budget caps, response caching and per-feature cost attribution | `reliability/r5_cost_control.py` |
| [R6: Online evaluation and drift](r6.md) | Monitor live quality, latency and cost samples to detect drift | `reliability/r6_online_eval_drift.py` |
| [R7: Action governance](r7.md) | Permissions, sandboxing and approval rules for agent actions | `reliability/r7_action_governance.py` |
| [R8: Supply chain](r8.md) | AI supply chain and dependency security checks | `reliability/r8_supply_chain.py` |
| [R9: Release safety](r9.md) | Shadow, canary and rollback for releasing a new version | `reliability/r9_release_safety.py` |

## How the modules connect

The modules are not isolated. R2's adversarial check reuses R1's scanner. R4 wraps the same three data tools that R1 defines. Reading them in order will make those links visible.

> **Note** These are **learning implementations**. They are small and readable on purpose, and each one has known limits that its page states. They show the shape of a real defence; they are not a finished security product. Treat each as a starting point, not a guarantee.

## How to read this track

1. Read each page, then run the offline demo it names. Most of this track runs without an API key, because the demos use fixtures or stand-in model calls.
2. Run the matching tests, for example `python -m pytest tests/test_guardrails.py -q`. The tests are the clearest statement of what each module promises.
3. Break something on purpose and watch the layer react. Each page has a "Try it" box for this.

> **Tip** Run these modules from the repository root. Where a page shows a command such as `python -m reliability.r4_resilience`, use the `-m` form: it makes Python find the `reliability` package.

Start with [R1: Guardrails](r1.md).
