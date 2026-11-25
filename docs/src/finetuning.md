---
title: Fine-tuning decisions
summary: Decide between prompting, few-shot, retrieval and fine-tuning, and check a training dataset before spending on it.
section: Foundations
order: 6
---

# Fine-tuning and build-versus-tune decisions

**The question this topic answers:** my model is not good enough yet. Should I change the prompt, add examples, add retrieval, or train it?

Fine-tuning means continuing a model's training on your own examples. It is powerful and often reached for too early. It costs money and time, it needs good data, and a tuned model is harder to change than a prompt. This topic gives you a decision model and a dataset checker, and it **does not train anything**.

## The idea in plain English

There is a ladder of ways to adapt a model, from cheapest and easiest to change at the bottom to heaviest at the top. Climb only as far as the evidence forces you to.

{{flow: Prompt only ~ cheapest | Few-shot ~ add examples | RAG ~ add knowledge | LoRA fine-tune ~ small adapter | Full fine-tune ~ heaviest}}

The module lists them in this order, cheapest first:

{{include levels/foundations/finetuning.py#_APPROACHES}}

Three terms help:

- **RAG (retrieval-augmented generation):** look up relevant documents at question time and give them to the model. Update the documents, not the model. See [retrieval](retrieval.md).
- **LoRA:** a *parameter-efficient* way to fine-tune that trains a small add-on (an adapter) instead of the whole model.
- **Full fine-tune:** update all the model's weights. The heaviest option.

## The advisor

{{include levels/foundations/finetuning.py#recommend_approach}}

Read it as a scoring sheet again. The rules, in plain words:

- **Fresh or changing knowledge** points to retrieval, because retrieval updates faster than training.
- **A strict output format on a stable task** points to LoRA fine-tuning.
- **Data volume** is a gate: 1,000 or more examples supports LoRA, 100 or more suits few-shot, and less points to prompt engineering.
- **Latency pressure** gives small points to LoRA and prompt-only (shorter prompts or smaller tuned models).
- **High domain shift with 1,000+ examples** can justify a full fine-tune.
- Prompt-only always gets a small baseline bonus: start simple.

The result lists the recommendation, a ranked scoreboard, the reasons, and one sentence of guidance.

## Worked examples

These come from running the function offline.

| Situation | Recommended | Scoreboard highlights |
| --- | --- | --- |
| 1,500 examples, strict stable format, no fresh knowledge | LoRA fine-tune | LoRA 3.5, prompt-only 0.5 |
| No data, no special needs (defaults) | Prompt only | Prompt-only 1.5, LoRA 0.5 |
| 1,500 examples, strict format, **and** fresh knowledge needed | LoRA fine-tune | LoRA 3.0, RAG 2.0 |

> **Warning** Look at the third row. Even with fresh knowledge needed, LoRA still wins because the data and format points outweigh the retrieval points. A person would probably want retrieval here. This is a **limit of the heuristic**, not a rule of nature, and it is a good reminder that these scores are a starting point for discussion. The function's own docstring says it is not a substitute for empirical evaluation. The test suite shows RAG winning for fresh knowledge in a smaller-data case; try varying `data_volume` yourself.

## Checking a dataset before you train

If you do decide to tune, bad data wastes the whole run. This function checks a chat-style dataset for common problems:

{{include levels/foundations/finetuning.py#validate_finetune_dataset}}

Each record should look like `{"messages": [...]}`, with at least one `user` and one `assistant` message. The validator counts records that:

- lack valid user and assistant roles,
- have an empty assistant reply, or
- are exact duplicates of an earlier record.

It then reports `quality_score` (valid records divided by total) and `ready_to_train`, which is true only when there are **at least 10 records**, a quality score of **0.9 or more**, and **no duplicates**. Those thresholds are teaching defaults, written in the code; real projects need far more data and richer checks.

A record with an empty answer, for example, is reported like this:

```json
{"total": 1, "valid": 0, "empty_completions": 1,
 "quality_score": 0.0, "ready_to_train": false,
 "issues": ["1 record(s) with empty assistant content"]}
```

> **Note** The validator checks structure only. It cannot tell whether your labels are *correct*, whether the data is representative, or whether it contains private information. See [privacy](privacy.md) for the last point.

## Run it

```bash
python levels/foundations/finetuning.py --data-volume 1500
python levels/foundations/finetuning.py --data-volume 50 --fresh-knowledge
```

Each prints a JSON recommendation, with no key and no cost. Over the API the advisor is `POST /foundations/adaptation/recommend` and the dataset check is `POST /foundations/finetune/validate`.

> **Note** In the command-line script, `--strict-format` defaults to on, so it is always on. Call the function directly to test the other case.

## Try it

> **Try it** 1) Hold everything else fixed and change `data_volume` through 0, 50, 100, 500, 1000. Where does the recommendation flip? 2) Find inputs that make RAG win. 3) Build a five-record dataset with one duplicate and one empty answer and read the issues. 4) Make a clean ten-record dataset and see `ready_to_train` become true.

## Common mistakes

- **Fine-tuning to add knowledge.** Tuning is better at *style and format* than at facts. Use retrieval for facts.
- **Skipping the cheap rungs.** Try a better prompt and a few examples first.
- **Tuning without an evaluation set.** You cannot tell if it helped. See [R2](r2.md).
- **Training on unchecked data.** Duplicates, empties and private data cost you twice.
- **Treating a heuristic as a verdict.**

## Check yourself

??? Why is fine-tuning usually a poor way to give a model fresh facts?
    Facts change, and retraining is slow and expensive. Retrieval lets you update the documents instead.

??? What is LoRA, in one sentence?
    A parameter-efficient fine-tuning method that trains a small adapter instead of the whole model.

??? What would make `ready_to_train` false even for a clean dataset?
    Having fewer than 10 records.

Next: [Retrieval](retrieval.md).
