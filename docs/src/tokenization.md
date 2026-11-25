---
title: Tokenization
summary: See how text becomes tokens, and how token counts turn into context limits and cost.
section: Foundations
order: 2
---

# Tokenization and context economics

**The question this topic answers:** what exactly am I paying for, and how much text fits in one call?

You met tokens in [How LLMs work](concepts.md). This page lets you *see* them. Models read and bill in tokens, and every model has a **context window**, a ceiling on tokens per call. Knowing your token count is the first step in controlling cost, avoiding cut-off input, and sizing anything you feed a model.

## The idea in plain English

A tokenizer chops text into pieces from a fixed vocabulary. Common words are often one piece. Rare strings, identifiers and punctuation get split into more pieces. That is why a short-looking CVE identifier can cost several tokens, while a plain English word costs one.

{{flow: Your text | Tokenizer ~ splits into pieces | Token ids ~ numbers | Count ~ cost and context}}

## Counting tokens

The module uses `tiktoken`, the tokenizer library used with OpenAI models, to count tokens exactly.

{{include levels/foundations/tokenization.py#count_tokens}}

The helper behind it picks the tokenizer that matches your model, and falls back to a general-purpose one if the model name is unknown:

{{include levels/foundations/tokenization.py#_get_encoding}}

> **Note** `tiktoken` is an optional package (the `foundations` and `tokens` extras). The first run may also need to fetch a tokenizer vocabulary file, so it can need a network connection once. The notebook `01_tokenization.ipynb` uses a built-in fallback of roughly four characters per token so it works fully offline, which is an approximation, not an exact count.

## Looking inside

`show_tokens` returns the first few tokens as an index, an id and the decoded text, so you can see where the cuts fall:

{{include levels/foundations/tokenization.py#show_tokens}}

Notice that a piece can include a leading space. That is normal: spaces are part of tokens.

## From tokens to a budget report

`tokenize_report` combines the count with the pricing helper from `vigil/pricing.py` to show how full the context window is and what the prompt would cost:

{{include levels/foundations/tokenization.py#tokenize_report}}

The fields to read:

| Field | Meaning |
| --- | --- |
| `token_count` | Exact tokens in your text for the chosen model |
| `context_limit` | The model's token ceiling, from the table in `vigil/pricing.py` |
| `pct_of_context` | How much of that ceiling this text uses |
| `est_cost_usd` | An **estimate** from indicative list prices; not a bill |
| `sample_tokens` | The first few pieces, so you can inspect the boundaries |

> **Warning** The cost is an estimate from prices copied into the code. Providers change prices, so use it for relative comparisons, not budgeting.

## Run it

```bash
python levels/foundations/tokenization.py "CVE-2021-44228 RCE in Log4j"
```

You should get a report dictionary and a table of the first tokens, each with its id and decoded piece. This needs `tiktoken`, so install the foundations extra if you have not: `pip install -e ".[foundations]"`.

The same report is available over the API at `POST /foundations/tokenize`, and in the Streamlit interface.

## Why it matters later

- **Cost.** Billing scales with tokens in and out. Longer prompts and longer answers cost more.
- **Cut-off.** If input plus reply exceeds the context window, something has to give. The L5 memory code builds a *budgeted* context for exactly this reason; see `build_budgeted_memory_context` in `levels/l5_memory.py`.
- **Chains and fan-out.** Every extra step you add in [L1](l1.md) or [L2](l2.md) repeats tokens, so token awareness shapes how you design them.

## Try it

> **Try it** 1) Tokenize `CVE-2021-44228`, then a plain English sentence of the same character length. Which costs more tokens per character? 2) Tokenize the same sentence in lower case, upper case and with extra punctuation. 3) Paste a long advisory and read `pct_of_context`. How many copies would it take to overflow the window? 4) Use `--model` with a different model name and compare counts.

The notebook `notebooks/01_tokenization.ipynb` has the same experiments with a one-line change per cell.

## Common mistakes

- **Counting characters or words instead of tokens.** The ratio changes with the text, so count properly.
- **Forgetting the reply.** The window covers your input *and* the model's output.
- **Assuming one tokenizer fits all models.** Different model families split text differently, so counts from one are only a rough guide for another.
- **Trusting the estimated cost.** It is a teaching figure from fixed prices.

## Check yourself

??? Why can a short identifier cost more tokens than a short English word?
    Tokenizers are built from common text. Common words are single pieces; rare strings, digits and symbols are split into several smaller ones.

??? What two limits do token counts control?
    Cost (you pay per token) and the context window (the maximum tokens per call, input plus output).

??? Is `est_cost_usd` a bill?
    No. It is computed from indicative list prices stored in `vigil/pricing.py`, which can be out of date.

Next: [Prompting techniques](prompting.md).
