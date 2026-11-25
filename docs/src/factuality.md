---
title: "Factuality and citations"
summary: Check each claim in an answer against the evidence, and abstain when it is unsupported.
section: Foundations
order: 8
---

# Factuality and citations

**The question this page answers:** how do I know an answer is backed by the evidence I gave the model, and not something it made up?

A model can produce a fluent, confident sentence that no source supports. This is often called a **hallucination**. Retrieval ([the previous page](retrieval.md)) gives the model real passages, but it does not *force* the model to stay inside them. So we check afterwards.

{{flow: Answer text | Split into claims | Compare each claim to the evidence | Supported or unsupported | Abstain or accept}}

The idea is **faithfulness**: the share of claims in an answer that the evidence supports.

> **Note** `levels/foundations/factuality.py` is a **lexical** checker: it measures word overlap between a claim and the evidence. It runs offline with no API key. It is a clear way to learn the idea, but it is a rough heuristic, not a fact-checker. The limits are spelled out below.

## Step 1: Break the answer into claims

A long answer is checked one sentence at a time, because one false sentence should not hide inside nine true ones:

{{include levels/foundations/factuality.py#split_claims}}

It splits on sentence endings and newlines. A real system might use a model to extract atomic claims; this splitter simply treats each sentence as a claim.

## Step 2: Reduce text to comparable terms

{{include levels/foundations/factuality.py#_tokens}}

It lowercases, drops filler words and keeps the rest. It also expands two security abbreviations so they can match the long form: `rce` becomes `remote code execution` and `dos` becomes `denial service`. Without that, a claim saying "RCE" would fail against evidence saying "remote code execution".

## Step 3: Score each claim against the evidence

A claim's support is the fraction of its terms found in the *best-matching* evidence snippet. The check then compares that to a threshold, which defaults to `0.45`:

{{include levels/foundations/factuality.py#factuality_check}}

The report gives you:

- `faithfulness_score`: supported claims divided by total claims.
- `unsupported_claims`: the sentences that failed.
- `abstain_recommended`: true as soon as **any** claim is unsupported. The safest behaviour for a system that must be right is to refuse, or to ask for review, rather than ship an unsupported statement.
- A per-claim result with the matching evidence excerpt, which is your **citation**.

### A worked example

Using the default demo evidence and one added false sentence, I ran this check offline:

```python
from levels.foundations.factuality import factuality_check

report = factuality_check(
    answer_text="Log4j has remote code execution and patch 2.17.1 is available. It was created by aliens.",
    evidence_snippets=[
        "CVE-2021-44228 allows remote code execution in Apache Log4j.",
        "Patch to Log4j 2.17.1 or later is recommended.",
    ],
)
```

The result: the first sentence scored `0.5`, above the `0.45` threshold, so it is supported. The second scored `0.0`. So `faithfulness_score` is `0.5`, `unsupported_claims` contains `It was created by aliens.`, and `abstain_recommended` is true.

## What this checker cannot do

Be clear-eyed about a word-overlap method:

- **It cannot detect contradiction.** "Log4j has **no** remote code execution" shares almost every word with the evidence, so it can score as supported. Overlap measures *topic*, not *truth*.
- **It cannot detect paraphrase.** A correct claim worded differently from the evidence may score low.
- **The threshold is a judgment call.** `0.45` is a default. Raise it and you reject more; lower it and you let more through.
- **It only knows the evidence you give it.** If the evidence is wrong or incomplete, a "supported" claim can still be false.

Production systems use stronger methods, for example a model that judges whether the evidence entails the claim, but the workflow is the same: split, compare, decide, cite.

## Run it

```bash
python levels/foundations/factuality.py
```

You should see a table with each claim, whether it is supported, its score and the evidence excerpt, followed by the full JSON report. Pass `--answer` and repeat `--evidence` to try your own text, and `--threshold` to move the cut-off.

## Try it

> **Try it** 1) Raise `--threshold` to `0.9` and watch supported claims turn unsupported. 2) Write a claim that *contradicts* the evidence using the same words (for example, adding the word "not") and see whether the checker catches it. It should not, and seeing that is the point. 3) Reword a true claim with synonyms and see its score fall.

## Common mistakes

- **Treating a high score as proof of truth.** It means the words overlap with the evidence.
- **Checking the whole answer at once.** Check claim by claim.
- **Ignoring abstention.** A system that always answers will sometimes answer without support.
- **Giving the checker no evidence.** With no snippets, every claim is unsupported.
- **Forgetting citations.** Showing the user the matching excerpt lets them verify for themselves.

## Check yourself

??? What is faithfulness?
    The share of an answer's claims that the supplied evidence supports.

??? Why does this checker fail to catch "Log4j has no remote code execution"?
    It measures shared words, and that sentence shares nearly all of them with the evidence. It cannot tell that "no" reverses the meaning.

??? When should a system abstain?
    When a claim has no adequate support in the evidence, especially in high-stakes work. Vigil's `abstain_recommended` flag is true if any claim is unsupported.

Next: [Privacy and safe logging](privacy.md) keeps secrets and personal data out of prompts and logs.
