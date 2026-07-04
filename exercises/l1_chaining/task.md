# Exercise L1 — Prompt Chaining

**Concept:** A chain runs several steps where **each step's output feeds the next**.
This is the backbone of L1 (extract → enrich → recommend).

## Your task

Open [start.py](start.py) and implement `run_chain(steps, initial)`:

- `steps` is a list of one-argument callables.
- Run them in order, passing the output of each step as the input to the next.
- Return the final output.
- If `steps` is empty, return `initial` unchanged.

## Run the grader

```bash
pytest exercises/l1_chaining -q
```

Compare with [solution.py](solution.py) when finished.
