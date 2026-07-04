# F9 — Learning Scaffolding: Notebooks & Exercises

- **Status:** Implemented
- **Axis:** Foundations (pedagogy) — how the project is learned
- **New:** `notebooks/`, `exercises/`
- **Depends on:** all levels (links them into an interactive path)

---

## Problem / Motivation

Everything in Vigil is CLI scripts + a Streamlit app. There's no place to **experiment**
(tweak temperature, diff embeddings, watch token counts) and no **"try it yourself"**
practice with solutions. Interactive notebooks and graded exercises are where GenAI
intuition is actually built; today the project explains but rarely lets the learner poke.

## Teaching Goal

**A learner opens a notebook, changes one parameter, and immediately sees the effect**
(cost, output, similarity), then completes short exercises that extend each level.
They get hands-on reps, not just reading.

## Goals

- **`notebooks/`** — a small set of runnable notebooks mapped to concepts:
  - `00_setup.ipynb` (env + first call), `01_tokenization.ipynb` (F4),
    `02_prompting.ipynb` (F6), `03_embeddings_rag.ipynb` (F1).
- **`exercises/`** — one short exercise per level (L0–L6) with a clear task, a stub to
  complete, and a hidden reference solution + a tiny test that grades it.
- **Index** — `notebooks/README.md` + `exercises/README.md` describing the path.
- **Offline-friendly** — notebooks degrade to cached/sample outputs when no API key.

## Non-Goals

- A full course platform / autograder service.
- Replacing the README learning path (this complements it).

## Design

```
notebooks/  → experiment live (concept per notebook)
exercises/  → task + stub + reference + test  (pytest grades the learner's solution)
```

## Proposed Files

- **New** `notebooks/00_setup.ipynb`, `01_tokenization.ipynb`, `02_prompting.ipynb`,
  `03_embeddings_rag.ipynb`, `notebooks/README.md`.
- **New** `exercises/l0_.../` … `exercises/l6_.../` each with `task.md`, `start.py`,
  `solution.py`, `test_exercise.py`.
- **Edit** `pyproject.toml` — extra `notebooks = ["jupyter>=1.0", "tiktoken>=0.7"]`.
- **Edit** `README.md` — add "Interactive learning" section linking notebooks/exercises.

## Data Models

None (pedagogy only).

## API & CLI Surface

- `pytest exercises/ -q` grades all completed exercises.
- `jupyter lab notebooks/` to explore.

## Tests

- Each exercise ships a `test_exercise.py` that passes against `solution.py` and fails
  against the unfilled `start.py` (proves the test is meaningful).
- A CI-light check that notebooks parse (nbformat) without executing network cells.

## Acceptance Criteria

- [ ] At least 4 notebooks run top-to-bottom (offline-friendly).
- [ ] At least 3 graded exercises (e.g., L0/L1/L4) with passing reference solutions.
- [ ] README points learners to the interactive path.

## Open Questions

- Execute notebooks in CI (nbmake) or just parse-check? Proposal: parse-check first.
