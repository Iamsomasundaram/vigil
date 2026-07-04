"""Exercise L1 — reference solution."""

from __future__ import annotations

from typing import Any, Callable


def run_chain(steps: list[Callable[[Any], Any]], initial: Any) -> Any:
    value = initial
    for step in steps:
        value = step(value)
    return value
