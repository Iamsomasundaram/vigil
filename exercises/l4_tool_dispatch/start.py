"""Exercise L4 — Tool dispatch.

Implement `dispatch_tool` to route a named tool call to its function, and to
degrade gracefully for unknown tools. See task.md.
"""

from __future__ import annotations

from typing import Any, Callable


def dispatch_tool(name: str, args: dict, registry: dict[str, Callable[..., Any]]) -> Any:
    """Route a tool call to `registry[name](**args)`.

    - Unknown tool → return {"error": f"Unknown tool: {name}"} (never raise).
    """
    raise NotImplementedError("Complete dispatch_tool — see task.md")
