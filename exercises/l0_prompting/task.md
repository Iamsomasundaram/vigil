# Exercise L0 — Constructing a Prompt

**Concept:** Every LLM interaction starts with a list of _messages_. The `system`
message sets the model's role and constraints; the `user` message carries the task.

## Your task

Open [start.py](start.py) and implement `build_analysis_messages(cve_id, system_role)`
so that it returns a two-element list of message dicts:

1. A `system` message whose `content` is the given `system_role`.
2. A `user` message asking the model to analyse the given `cve_id`.

Each message must be a dict with exactly the keys `role` and `content`.

## Run the grader

```bash
pytest exercises/l0_prompting -q
```

It should fail until you fill in the function, then pass. Compare your answer with
[solution.py](solution.py) once you're done.
