---
title: Learning path
summary: Every level, notebook and exercise in the order to do them.
section: Practice
order: 1
---

# Learning path

Do the **Core** path first. It is enough to understand how an AI system becomes an agent. The rest goes deeper and can be done in any order that interests you.

## Core path

| Step | Do this | Time | Guide page |
| --- | --- | --- | --- |
| 1 | Install and run the tests | 15 min | [Getting started](getting-started.md) |
| 2 | Read the theory | 20 min | [How LLMs work](concepts.md) |
| 3 | Notebook `00_setup.ipynb` | 15 min | `notebooks/` |
| 4 | **L0**: a single call | 30 min | [L0](l0.md) |
| 5 | Exercise `l0_prompting` | 20 min | `exercises/l0_prompting` |
| 6 | **L1**: chaining and structured output | 45 min | [L1](l1.md) |
| 7 | Exercise `l1_chaining` | 20 min | `exercises/l1_chaining` |
| 8 | **L2**: parallel agents | 45 min | [L2](l2.md) |
| 9 | **L3**: routing | 45 min | not written yet, read `levels/l3_routing.py` |
| 10 | **L4**: tool use | 60 min | not written yet, read `levels/l4_tool_use.py` |
| 11 | Exercise `l4_tool_dispatch` | 30 min | `exercises/l4_tool_dispatch` |

The times are rough estimates for a first read, not measurements.

## Then go further

| Topic | Where to look |
| --- | --- |
| Memory and feedback loops (L5) | `levels/l5_memory.py` (needs PostgreSQL) |
| Autonomous monitoring (L6) | `levels/l6_autonomous.py` (needs PostgreSQL) |
| Reading PDFs and images (L4b) | `levels/l4b_multimodal.py` |
| Agent designs: ReAct, plan-and-execute, reflection, multi-agent | `architectures/` |
| Making agents safe and reliable: guardrails, evaluation, observability, cost control | `reliability/` |
| Retrieval, tokenization, prompting, privacy and more | `levels/foundations/` and the notebooks |
| The full feature list and its status | `specs/progress-board.md` |
| Every module, function and endpoint | [Code reference](reference.md) |

> **Tip** Tokenization, prompting and embeddings each have a runnable notebook: `01_tokenization`, `02_prompting` and `03_embeddings_rag`. They are the quickest way to build intuition, because you change a value and watch the result.

## How to learn from each level

1. Read the guide page first so you know what to look for.
2. Run the level and read its output.
3. Open the level's Python file. The comments at the top explain the concepts.
4. Change one thing and run it again.
5. Do the exercise, if there is one.
6. Answer the self-check questions out loud.

## When you get stuck

Search the guide with the box at the top (press `/`), check the [glossary](glossary.md), then the troubleshooting table in the project README.
