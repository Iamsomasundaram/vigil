---
title: Model selection
summary: Choose a model tier from your constraints, and see how a request maps onto the Claude Messages API.
section: Foundations
order: 5
---

# Model selection (and the Claude bridge)

**The question this topic answers:** which model should do this job, and what changes if it is a different provider's?

Models come in tiers. Small, fast ones are cheap and good at simple jobs. Larger ones reason better, cost more and answer more slowly. Using the biggest model for everything wastes money; using the smallest for everything gives poor answers where it matters. This topic shows a transparent way to think about the trade-off.

## The idea in plain English

Think of hiring. You would not use a senior consultant to sort the post, nor a junior to sign off a contract with large consequences. Match the person to the task. For models, the facts that matter are: how hard the task is, how fast you need the answer, how many requests you will make, how tight the budget is, and how bad a wrong answer would be.

{{flow: Task facts ~ difficulty, speed, volume, cost, stakes | Scoring ~ points per tier | Recommended tier ~ plus reasons}}

## The tier profiles

The module describes three Claude tiers as plain data:

{{include levels/foundations/model_selection.py#_CLAUDE_TIERS}}

> **Warning** The numbers here are **relative teaching proxies**, as the code comment says, not billing figures, benchmarks or measured latency. They only rank the tiers against each other. For real prices and capabilities, use the provider's current documentation.

## The recommender

{{include levels/foundations/model_selection.py#recommend_model}}

Read it as a scoring sheet:

- Task complexity gives the first points: low favours Haiku, medium favours Sonnet, high favours Opus.
- Latency sensitivity, cost sensitivity and high volume push towards the cheaper, faster tier.
- High stakes pushes towards Opus.
- Sonnet always gets a small bonus, so it is the safe default when nothing else is decisive.

The answer includes the winner, a ranked list with scores, the reasons that fired, and an **escalation hint**: start on the cheaper tier and move up only when evaluations show you need to.

## Worked examples

These come from running the function offline; the scores follow directly from the rules above.

| Inputs | Result (score) |
| --- | --- |
| Low complexity, latency sensitive | Haiku (3.5), then Sonnet (0.75), then Opus (0) |
| Defaults (medium complexity) | Sonnet (2.75), then Haiku (0), then Opus (0) |
| High complexity, high stakes | Opus (3.5), then Sonnet (0.75), then Haiku (0) |

## Run it

```bash
python levels/foundations/model_selection.py --complexity low --latency
python levels/foundations/model_selection.py --complexity high --high-stakes
```

Each prints a JSON recommendation. It needs no key and makes no model call. Over the API it is `POST /foundations/model-select`.

> **Note** The command-line flags cover complexity, latency, cost and high stakes. The `high_volume` input exists in the function but has no flag, so call the function directly to use it.

## Bridging to another provider

Most of Vigil talks to OpenAI-style APIs. Claude's Messages API has a slightly different shape, and the module `vigil/claude_provider.py` shows the difference without touching the rest of the code. The key difference: Claude takes the system prompt as a **separate top-level field**, not as a message with a `system` role.

{{include vigil/claude_provider.py#map_messages_to_claude}}

So this list:

```python
[
    {"role": "system", "content": "You are a security analyst."},
    {"role": "user", "content": "Explain CVE-2021-44228."},
]
```

becomes a `system` string plus a list of `user` and `assistant` messages whose content is a list of text blocks. The mapping is pure code, so it can be tested offline, and it is exposed at `POST /claude/map-messages`.

The function that actually calls the API, `acomplete_claude`, imports the `anthropic` package only when called, and fails with a clear message if it is missing (`pip install -e ".[claude]"`). The default model name comes from the `ANTHROPIC_MODEL` environment variable, with a fallback written in the code. Model names change over time, so check that default against the provider's current list before relying on it.

> **Note** In this teaching bridge, tool and function messages are deliberately ignored by the mapper.

## Try it

> **Try it** 1) Call `recommend_model` with `cost_sensitive=True` and `high_volume=True` and read which reasons fired. 2) Find inputs where Sonnet and Haiku tie or nearly tie and see which wins. 3) Add a fourth tier to `_CLAUDE_TIERS` and see what else you must change. 4) Map a three-message conversation with `map_messages_to_claude` and inspect the output shape.

## Common mistakes

- **Picking a model by reputation.** Choose by measured results on your own task.
- **Using the biggest model by default.** Start small, then escalate when evidence says so.
- **Reading the relative scores as real numbers.** They are teaching proxies.
- **Mixing up the system prompt placement across providers.** This is exactly what the mapper handles.
- **Hard-coding a model name.** Keep it in configuration, because names and availability change.

## Check yourself

??? Why does Sonnet get a bonus no matter what?
    It is the balanced default for most production work, so it should win when no constraint clearly points elsewhere.

??? What does the escalation hint recommend?
    Start on the cheaper tier and move up only when evaluations show it is necessary.

??? How does the Claude Messages API treat the system prompt differently from the chat format used in L0?
    It is a top-level `system` parameter rather than a message with the `system` role.

Next: [Fine-tuning decisions](finetuning.md).
