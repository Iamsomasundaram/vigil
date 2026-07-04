# Exercise L4 — Tool Dispatch

**Concept:** In a tool-using agent, the model emits a tool _name_ and _arguments_;
your code must route that call to the right Python function — and fail safely when the
model asks for a tool that doesn't exist.

## Your task

Open [start.py](start.py) and implement `dispatch_tool(name, args, registry)`:

- `registry` maps a tool name to a callable.
- If `name` is in `registry`, call it with `**args` and return its result.
- If `name` is **not** in `registry`, return `{"error": f"Unknown tool: {name}"}`
  (do not raise).

## Run the grader

```bash
pytest exercises/l4_tool_dispatch -q
```

Compare with [solution.py](solution.py) when finished.
