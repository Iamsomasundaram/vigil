# F4 — Tokenization & Context Economics

- **Status:** Draft
- **Axis:** Foundations (GenAI literacy)
- **New module:** `levels/foundations/tokenization.py` + notebook
- **Depends on:** none (pure fundamentals); complements R5 (cost control)

---

## Problem / Motivation

Tokens are referenced everywhere (cost lines, `max_tokens`, the glossary) but a learner
never **sees** tokenization happen. They don't build intuition for why
"CVE-2021-44228" is ~6 tokens, how context windows fill up, or how token count maps to
cost and latency. This intuition underpins prompt design, RAG sizing, and cost control.

## Teaching Goal

**A learner tokenizes real strings with `tiktoken`, counts tokens for a full prompt, and
sees the live cost/length trade-off.** They learn what a token is, how BPE splits text,
context-window budgeting, and the token→cost relationship.

## Goals

- **Tokenizer hands-on** — `count_tokens(text, model)`, `show_tokens(text)` that prints
  the token boundaries and ids.
- **Prompt budgeting** — given system+user+history, show tokens used vs the model's
  context limit, and the projected cost (reuse `vigil/pricing.py`).
- **Comparisons** — same sentence in English vs code vs JSON vs non-English to show
  token density differences.
- **Interactive notebook** — `notebooks/01_tokenization.ipynb` to experiment live.

## Non-Goals

- Training a tokenizer; deep BPE theory (link out, keep it practical).

## Design

```
text ─► tiktoken.encoding_for_model(MODEL) ─► [ids] ─► count + boundaries
prompt parts ─► sum tokens ─► vs context_limit ─► pricing.estimate_cost_usd()
```

## Proposed Files

- **New** `levels/foundations/__init__.py`, `levels/foundations/tokenization.py` — CLI:
  `python -m levels.foundations.tokenization "some text"`.
- **New** `notebooks/01_tokenization.ipynb`.
- **Edit** `vigil/pricing.py` — add `CONTEXT_LIMITS` map + `budget_report()` helper.
- **Edit** `vigil/api.py` — `POST /foundations/tokenize` `{text}` → token report.
- **Edit** `pyproject.toml` — extra `foundations = ["tiktoken>=0.7"]`.
- **New** `tests/test_tokenization.py` — counts match `tiktoken`; budget math correct.
- **Edit** `ui/app.py` — a "Tokenization" page under a new "Foundations" nav group.

## Data Models (`vigil/models.py`)

```python
class TokenReport(_Base):
    model: str
    text_preview: str
    token_count: int
    context_limit: int
    pct_of_context: float
    est_cost_usd: float
    sample_tokens: list[str]   # first N decoded tokens
```

## API & CLI Surface

- `POST /foundations/tokenize` `{text, model?}` → `TokenReport`.
- CLI: `python -m levels.foundations.tokenization "CVE-2021-44228 RCE"`.

## Tests (`tests/test_tokenization.py`)

- `count_tokens` matches `tiktoken` for known strings.
- `budget_report` flags over-limit prompts; cost matches pricing.
- Skips gracefully if `tiktoken` not installed.

## Acceptance Criteria

- [ ] Token counts match `tiktoken` exactly for sample strings.
- [ ] Budget report shows tokens vs context limit and projected cost.
- [ ] Notebook runs top-to-bottom; UI page renders a live token report.

## Open Questions

- Use exact provider context limits or a documented constant map? Proposal: constant map.
