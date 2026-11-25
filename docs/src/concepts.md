---
title: How LLMs work
summary: Tokens, messages, temperature, context windows and cost, in just enough depth to read the code.
section: Start here
order: 3
---

# How LLMs work (just enough)

You do not need the maths. You need five ideas, because every level in Vigil is built from them.

## 1. A language model predicts the next piece of text

A large language model (LLM) is a program trained on a huge amount of text. Given some text, it predicts what should come next, one small piece at a time, until it decides to stop. Everything else, such as answering questions, writing code or following instructions, comes out of doing that very well.

Two consequences matter for Vigil:

- The model **does not look things up**. It answers from patterns it learned during training, so it can be confidently wrong about a specific CVE. Later levels fix this by giving it tools (L4).
- The model **does not remember** earlier calls. Each call starts blank. Anything it should know, you must send again (L5 is about doing that well).

## 2. Tokens

Models read and write **tokens**, not letters or words. A token is a chunk of text, roughly four characters or three quarters of a word in English.

<div class="flow" role="img"><div class="node"><b>"Log4Shell is critical"</b><small>your text</small></div><span class="arr">→</span><div class="node">Log</div><div class="node">4</div><div class="node">Shell</div><div class="node"> is</div><div class="node"> critical</div></div>

The split above is only an illustration; real tokenizers cut text in their own ways.

Tokens matter because **you are billed per token** and because every model has a **context window**, a maximum number of tokens it can handle in one call (your input plus its reply). The notebook `01_tokenization.ipynb` lets you see this directly.

## 3. Messages and roles

You do not send the model a single string. You send a **list of messages**, each with a *role*:

| Role | Who writes it | What it is for |
| --- | --- | --- |
| `system` | You, the developer | The job description: who the model is and how it should behave |
| `user` | You or your end user | The actual task or question |
| `assistant` | The model | Its earlier replies, which you send back to continue a conversation |

In code that is just a list of dictionaries:

```python
messages = [
    {"role": "system", "content": "You are a senior security analyst."},
    {"role": "user", "content": "Explain CVE-2021-44228."},
]
```

This list is the atomic unit of every level in Vigil. Even the autonomous agent in L6 is, underneath, building and sending lists like this.

## 4. Temperature

Temperature controls how adventurous the next-token choice is.

- **Low (0.0 to 0.3)**: the model sticks to the most likely wording. Answers are consistent. Good for facts and structured data.
- **High (0.8 and above)**: the model takes less likely paths. Answers vary and feel more creative. Good for brainstorming, risky for facts.

Vigil uses low values (0.1 to 0.2) because a security team wants steady, careful answers. Even at 0.0 you cannot assume identical output every time.

## 5. Cost and latency

A call has a price and a delay, and both grow with the number of tokens in and out. That is why later levels care about prompt size, caching and picking a cheaper model for easy jobs.

> **Note** Vigil shows a cost per run, but it is an **estimate** from list prices stored in `vigil/pricing.py`. Provider prices change and are not synced, so treat the number as a rough guide, not a bill.

## What a model call looks like

{{flow: Your messages ~ system + user | The model ~ predicts tokens | Reply text ~ plus token counts}}

The reply also reports how many tokens went in and out. Vigil adds these up to give each run its token and cost summary.

## Check yourself

??? Why can a model be confidently wrong about a specific CVE?
    It answers from patterns in its training data, not from a live database. If it never saw reliable details about that CVE, or saw them only in passing, it may produce a fluent answer that is wrong. Tools (L4) and retrieval (the F-series) exist to ground it in real data.

??? A call fails because the input is too long. What limit did you hit?
    The context window: the maximum tokens for input plus output in one call.

??? Why is temperature set low for a security analysis?
    You want consistent, careful answers. High temperature trades consistency for variety, which is the wrong trade for facts.

Ready for code? Continue to [Level 0](l0.md).
