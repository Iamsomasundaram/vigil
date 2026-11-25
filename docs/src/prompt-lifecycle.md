---
title: Prompt lifecycle
summary: Version prompts, replay them on fixed examples, and compare versions before you ship a change.
section: Foundations
order: 4
---

# Prompt lifecycle and experiments

**The question this topic answers:** when I change a prompt, how do I know the new one is better, and how do I get back if it is not?

On [the previous page](prompting.md) a prompt was a piece of craft. In a real product a prompt is **code**: it changes over time, other people depend on it, and a bad edit can quietly make things worse. This topic treats prompts the way you treat software: give each one a version, test it on the same inputs, compare, then ship or roll back.

## The idea in plain English

Keep a numbered list of prompt versions. When you want to change one, run **both** the old and the new version over the same fixed examples, score each answer, and compare. You ship the new one only if the numbers say it is better.

{{flow: Prompt versions ~ v1, v2 | Replay ~ same fixed examples | Score ~ per item | Compare ~ ship or roll back}}

## Versions live in data, not in code

Versions are stored as records in `data/prompts/f14_prompt_versions.json`. Each has an id, a name, a template with a `{item}` placeholder, and notes:

```json
{
  "id": "v1",
  "name": "baseline-concise",
  "template": "Classify severity for {item}. Keep answer concise.",
  "notes": "Low-token baseline"
}
```

The second record, `v2` (`structured-risk-first`), asks for the severity first, then two risks, then two actions. If the file is missing, the module falls back to the same two versions built into the code.

## Replaying a version

Replay fills the template with each example and scores the result:

{{include levels/foundations/prompt_lifecycle.py#replay_version}}

## An important honesty note about the scorer

Look at the function that produces `quality_score`:

{{include levels/foundations/prompt_lifecycle.py#_simulate_quality}}

This is **not** a real quality judge. It is a deterministic, hand-written stand-in that rewards prompts for containing words like "risk", "action" and "structured". It exists so the *workflow* runs offline, with no model and no cost, and gives the same result every time.

> **Warning** Because the scorer only reads the prompt text, `v2` "wins" mostly because it contains more of those words. Do not read that as evidence that structured prompts are better. In real work you would replace this function with scoring of the model's actual outputs, for example with the evaluation approach in [R2](r2.md).

## Comparing two versions

{{include levels/foundations/prompt_lifecycle.py#compare_versions}}

It replays both versions over your items and reports, per item, which one won, then an overall winner by average quality. Version ids that do not exist raise an error.

## Run it

```bash
python levels/foundations/prompt_lifecycle.py --a v1 --b v2
```

You should see a table with one row per item (three CVE ids by default), the quality score for each version, and a winner column, followed by the same data as JSON. Add your own with `--item`. The same comparison is available at `GET /foundations/prompt-versions` and `POST /foundations/prompt-versions/compare`.

> **Note** `--item` adds to the default list rather than replacing it, so your items run alongside the three defaults.

## The part the code leaves to you: the decision rule

The module gives you the comparison, not the ship decision. Before you compare, decide your rule, for example: "ship only if the new version wins on at least two thirds of items and costs no more than 20% more tokens." Fixing the rule first stops you from picking whichever numbers look good afterwards. The `token_proxy` field (a word count) is there so you can weigh cost alongside quality.

## Try it

> **Try it** 1) Add a `v3` to `data/prompts/f14_prompt_versions.json` and compare it with `v2`. 2) Write a deliberately bad prompt that avoids the scorer's keywords and see how it ranks, then ask whether that ranking is fair. 3) Replace `_simulate_quality` with a function that scores something you can measure, such as length, and re-run. 4) Break the JSON file on purpose and note the error.

## Common mistakes

- **Editing a prompt in place with no version.** You cannot compare or roll back.
- **Testing on one example.** Use a fixed set that covers easy and hard cases.
- **Changing the examples between runs.** Then the comparison is meaningless.
- **Trusting a stand-in scorer.** Know what the score actually measures.
- **Deciding the rule after seeing the results.**

## Check yourself

??? Why replay on the same fixed examples?
    So any difference in score comes from the prompt change, not from different inputs.

??? Why does `v2` score higher in the demo, and should you trust that?
    The simulated scorer rewards certain words that `v2` contains. It shows the workflow, not real quality, so no.

??? What should you decide before you run a comparison?
    The ship-or-rollback rule: the thresholds for quality and cost that a new version must meet.

Next: [Model selection](model-selection.md).
