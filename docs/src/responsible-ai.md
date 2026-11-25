---
title: "Responsible AI"
summary: Flag harmful text with a simple moderation filter, and measure whether outcomes are fair across groups.
section: Foundations
order: 10
---

# Responsible AI

**The question this page answers:** before I ship an AI feature, how do I check that it does not produce harmful text and does not treat groups of people unfairly?

Two separate checks live in `levels/foundations/responsible_ai.py` (spec F23):

1. **Moderation**: does a piece of text contain content a policy would block?
2. **Fairness**: do different groups receive positive outcomes at similar rates?

{{fan: A batch of samples | Moderate the texts, Measure outcome rates per group | One report with a ship or do-not-ship flag}}

> **Note** Both checks are **illustrative** and run offline. The moderation filter is a short word list, and the code comments say plainly that it is "not a production classifier". Treat this page as a way to learn the *shape* of responsible-AI checks, not as a safety guarantee.

## Check 1: Moderation

Moderation looks for categories of content you do not want to pass through. Vigil's version is a small set of word patterns, one list per category:

{{include levels/foundations/responsible_ai.py#_MODERATION_PATTERNS}}

`moderate_text` lowercases the text, looks for any match and returns the categories, the matched words and an action:

{{include levels/foundations/responsible_ai.py#moderate_text}}

Running it offline on `You stupid loser` flags the `harassment` category, lists `stupid` and `loser` as the matched spans, and returns the action `block`. Clean text returns `allow`.

### Why a word list is not enough

A list like this is easy to understand and easy to fool, in both directions:

- **False positives.** The `hate` rule used to contain the bare word `kill`, so `This exploit will kill the process` was blocked. It now only matches `exterminate`, `inferior race`, `subhuman`, or `kill` followed by `all` or `every(one)` and a word, so that sentence passes. The general problem remains: in security work, "attack", "bomb" and similar words appear in perfectly normal text, and any word list will misfire somewhere.
- **False negatives.** Anything harmful that avoids the listed words, or hides them with odd spelling, sails through.
- **No context.** The filter cannot tell a quotation from a threat.

Production systems use trained classifiers or provider moderation services, plus human review. The lesson here is the *placement*: moderation runs on inputs and outputs, and its result decides allow or block.

## Check 2: Fairness

If your system makes yes or no decisions that affect groups of people, such as who gets flagged, approved or escalated, you should check whether the outcomes are even. Vigil computes the simplest standard measure: **selection rate parity**.

{{include levels/foundations/responsible_ai.py#fairness_report}}

Each outcome is a group name and a yes or no. The function works out:

1. the **selection rate** for each group: positives divided by total,
2. the **disparate-impact ratio**: the lowest group's rate divided by the highest, and
3. whether that ratio reaches **0.8**, often called the "80% rule", a common rule of thumb for spotting a gap.

### A worked example

Take the demo data in the module's own `main()`: group A has two out of two positive, group B has one out of two. The selection rates are `1.0` and `0.5`. The ratio is `0.5 / 1.0 = 0.5`, which is below `0.8`, so `passes_80pct_rule` is false.

## The combined report

`responsible_ai_report` runs both checks over a batch and sets a `safe_to_ship` flag that is true only if **no text was flagged and the fairness check passed**. With the demo's two texts and the data above, one text is flagged and the ratio fails, so `safe_to_ship` is false.

This is also available from the API as `POST /foundations/responsible-ai`.

## What this does not tell you

- **Parity is one definition of fairness among several.** Two groups can have equal rates and still be treated unfairly in other ways, and sometimes different rates are legitimate. The ratio is a flag to investigate, not a verdict.
- **Small samples mislead.** Two outcomes per group, as in the demo, show the mechanism but prove nothing.
- **You must supply the groups and outcomes.** The module cannot discover who is affected.
- **A passing result is not clearance.** It means this one test did not fail.

> **Warning** Do not use these checks as legal or compliance evidence. Treat a fail as a prompt to look closer, and a pass as only the start.

## Run it

```bash
python levels/foundations/responsible_ai.py
python levels/foundations/responsible_ai.py --text "This tool is great" --text "You stupid loser"
```

You should see a JSON report with the per-text moderation results, the fairness figures and `safe_to_ship`.

## Try it

> **Try it** 1) Add a harmless sentence containing a listed word, such as one that says "the bomb squad arrived", and look for a false positive. 2) Add a sentence of genuinely harmful content that avoids every listed word and see it pass. 3) Build outcomes where both groups have the same rate and confirm the ratio is `1.0`.

## Common mistakes

- **Treating a short word list as a safety system.**
- **Moderating only the user's input.** Check the model's output too.
- **Testing fairness on a handful of cases.**
- **Reading a pass as "fair".** It only means this test did not fail.
- **Letting a flag silently pass.** Decide in advance what happens on a block: refuse, rewrite, or send to a person.

## Check yourself

??? Why was `This exploit will kill the process` a problem for this filter, and what changed?
    It contained a listed word, so it was blocked even though it is harmless technical language. That is a false positive. The rule now needs a more specific phrase, so that sentence passes, but word lists can always misfire on other text.

??? What is the disparate-impact ratio?
    The lowest group's selection rate divided by the highest group's. A value under 0.8 fails the 80% rule of thumb.

??? When is `safe_to_ship` true?
    Only when no text was flagged and the fairness ratio is at least 0.8.

Next: [Semantic caching](semantic-cache.md) cuts cost and delay by reusing answers to similar questions.
