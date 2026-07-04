"""Exercise L4 — reference solution."""

from __future__ import annotations

from typing import Any, Callable


def dispatch_tool(name: str, args: dict, registry: dict[str, Callable[..., Any]]) -> Any:
    fn = registry.get(name)
    if fn is None:
        return {"error": f"Unknown tool: {name}"}
    return fn(**args)
