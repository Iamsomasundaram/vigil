---
title: Foundations overview
summary: The F-series: focused lessons on the building blocks under every level.
section: Foundations
order: 1
---

# Foundations overview

**The question this section answers:** what do I need to understand *underneath* the levels to build AI systems that are cheap, steady and trustworthy?

The levels (L0 to L6) teach a capability ladder. The **foundations** (the F-series) teach the ideas that sit under every rung: how text becomes tokens, how prompts are written and versioned, how to pick a model, when to train one, how retrieval works, and how to keep answers honest and private.

Each foundation is a small module in `levels/foundations/`, with a spec in `specs/`, tests in `tests/`, and (for the first few) a runnable notebook. Most can be run with **no API key**, because they are deterministic helpers that teach a decision, not live model calls.

{{flow: Tokens ~ what costs money | Prompts ~ what you ask | Model choice ~ who answers | Adaptation ~ tune or not | Retrieval ~ what it knows}}

## How this maps onto the rest of the project

| If you are on... | Read this foundation | Why it helps |
| --- | --- | --- |
| [L0](l0.md), reading `max_tokens` and cost lines | [Tokenization](tokenization.md) | See exactly what a token is and how it turns into cost and context limits |
| [L0](l0.md) and [L1](l1.md), writing system prompts | [Prompting techniques](prompting.md) | Compare zero-shot, few-shot and chain-of-thought on one task |
| Changing a prompt in a real project | [Prompt lifecycle](prompt-lifecycle.md) | Version, replay and compare prompts before shipping a change |
| Choosing which model to call | [Model selection](model-selection.md) | A transparent way to weigh complexity, speed, cost and risk |
| Wondering whether to fine-tune | [Fine-tuning decisions](finetuning.md) | Decide between prompting, few-shot, RAG and tuning, and check a dataset first |
| [L5](l5.md), recalling past work | [Retrieval](retrieval.md) | How search over your own documents works and is measured |

## The notebooks

Three notebooks in `notebooks/` let you experiment offline. They link back to the real code.

| Notebook | Pairs with |
| --- | --- |
| `01_tokenization.ipynb` | [Tokenization](tokenization.md) |
| `02_prompting.ipynb` | [Prompting techniques](prompting.md) |
| `03_embeddings_rag.ipynb` | [Retrieval](retrieval.md) |

Run them with `jupyter lab notebooks/` (see [Getting started](getting-started.md)).

## Pages in this section

| Page | Spec | Code | Needs a key? |
| --- | --- | --- | --- |
| [Tokenization](tokenization.md) | F4 | `levels/foundations/tokenization.py` | No |
| [Prompting techniques](prompting.md) | F6 | `levels/foundations/prompting.py` | Only for the live comparison |
| [Prompt lifecycle](prompt-lifecycle.md) | F14 | `levels/foundations/prompt_lifecycle.py` | No |
| [Model selection](model-selection.md) | F22 | `levels/foundations/model_selection.py` | No |
| [Fine-tuning decisions](finetuning.md) | F21 | `levels/foundations/finetuning.py` | No |
| [Retrieval](retrieval.md) | F11, F12, F16 | `levels/foundations/retrieval_quality.py` | No |
| [Factuality](factuality.md) | F13 | `levels/foundations/factuality.py` | No |
| [Privacy](privacy.md) | F15 | `levels/foundations/privacy.py` | No |
| [Responsible AI](responsible-ai.md) | F23 | `levels/foundations/responsible_ai.py` | No |
| [Semantic cache](semantic-cache.md) | F24 | `levels/foundations/semantic_cache.py` | No |
| [Incident-response theme](incident-ops.md) | T1 | `levels/themes/incident_ops.py` | No |

> **Note** "No key" means the helper itself runs offline. The same modules are also exposed through the API under `/foundations/...`, so the Streamlit interface can call them too.

## A pattern you will see again and again

Several foundations are **heuristic advisors**: a small function scores a few options from the facts you give it and returns a recommendation plus its reasons. They are deliberately simple so you can read every line, and each docstring says so. They are a starting point for a decision, never a substitute for measuring on your own data (which is what [evaluation](r2.md) is for).

Start with [Tokenization](tokenization.md).
