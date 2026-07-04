# F6 — Prompt Engineering Techniques

- **Status:** Draft
- **Axis:** Foundations (GenAI literacy)
- **New module:** `levels/foundations/prompting.py` + notebook
- **Depends on:** L0/L1 (system prompts, structured output)

---

## Problem / Motivation

Vigil _uses_ good prompts but never **teaches** prompt engineering as a topic. A learner
doesn't see, on the same task, the difference between zero-shot, few-shot, and
chain-of-thought, nor how prompt templates and role design change outputs. This is the
cheapest, highest-leverage GenAI skill and it's currently implicit.

## Teaching Goal

**A learner runs the same CVE task with zero-shot, few-shot, and chain-of-thought
prompts and compares the outputs and token cost.** They learn role design, few-shot
exemplars, CoT, delimiters, and prompt templating — and when each is worth its tokens.

## Goals

- **Technique catalog** — `zero_shot()`, `few_shot()`, `chain_of_thought()`,
  `self_consistency()` over one shared task (severity classification).
- **Prompt templates** — a tiny `render(template, **vars)` showing variable injection and
  delimiter discipline (untrusted data fenced — reuse R1 isolation).
- **Side-by-side comparison** — output + tokens + cost per technique (reuse pricing/F4).
- **Notebook** — `notebooks/02_prompting.ipynb` to tweak and re-run live.

## Non-Goals

- Automated prompt optimization / DSPy (future spec).
- Fine-tuning (covered conceptually in F-notes, not here).

## Design

```
task: classify CVE severity
  ├─ zero_shot         (instruction only)
  ├─ few_shot          (k labeled exemplars)
  ├─ chain_of_thought  ("think step by step", then extract)
  └─ self_consistency  (n samples → majority vote)
→ compare output / tokens / cost
```

## Proposed Files

- **New** `levels/foundations/prompting.py` — techniques + CLI compare.
- **New** `notebooks/02_prompting.ipynb`.
- **Edit** `vigil/api.py` — `POST /foundations/prompt-compare` `{cve_id}`.
- **New** `tests/test_prompting.py` — each technique builds the expected message shape;
  self-consistency aggregates votes (model stubbed).
- **Edit** `ui/app.py` — "Prompt Techniques" page under the Foundations group.

## Data Models (`vigil/models.py`)

```python
class PromptComparison(_Base):
    task: str
    results: list[dict]   # technique, output, tokens, est_cost_usd
    notes: str
```

## API & CLI Surface

- `POST /foundations/prompt-compare` `{cve_id}` → `PromptComparison`.
- CLI: `python -m levels.foundations.prompting CVE-2021-44228`.

## Tests (`tests/test_prompting.py`)

- Few-shot includes the exemplars; CoT includes a reasoning instruction; zero-shot doesn't.
- Self-consistency runs n samples and majority-votes (stubbed).
- Untrusted data is fenced with delimiters.

## Acceptance Criteria

- [ ] One task runs under 4 techniques with a comparison of output/tokens/cost.
- [ ] Templates inject variables and fence untrusted data.
- [ ] Notebook runs; UI page renders the comparison.

## Open Questions

- Number of few-shot exemplars and self-consistency samples (propose 3 and 5).
