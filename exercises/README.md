# Vigil Exercises — Try It Yourself

Short, offline, graded exercises that reinforce each level. Every exercise folder has:

| File               | Purpose                                                       |
| ------------------ | ------------------------------------------------------------- |
| `task.md`          | What to build                                                 |
| `start.py`         | A stub for **you** to complete (raises `NotImplementedError`) |
| `solution.py`      | The reference answer (peek after you try)                     |
| `test_exercise.py` | A grader that imports your `start.py`                         |

## How to do an exercise

1. Read `task.md`.
2. Edit `start.py` until the grader passes:

   ```bash
   pytest exercises/l0_prompting -q
   ```

3. Compare your answer with `solution.py`.

## Available exercises

| Exercise                                     | Concept                            | Maps to |
| -------------------------------------------- | ---------------------------------- | ------- |
| [l0_prompting](l0_prompting/task.md)         | Building system/user messages      | L0      |
| [l1_chaining](l1_chaining/task.md)           | Threading step outputs in a chain  | L1      |
| [l4_tool_dispatch](l4_tool_dispatch/task.md) | Routing tool calls, failing safely | L4      |

> The project's own test suite (`tests/test_exercises.py`) grades each `solution.py`
> and verifies each `start.py` is still an unfinished stub — so you can trust the
> reference answers are correct.
