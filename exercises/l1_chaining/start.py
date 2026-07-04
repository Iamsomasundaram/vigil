"""Exercise L1 — Prompt chaining.

Implement `run_chain` so each step's output feeds the next. See task.md.
"""

from __future__ import annotations

from typing import Any, Callable


def run_chain(steps: list[Callable[[Any], Any]], initial: Any) -> Any:
    """Run `steps` in order, threading each output into the next step.

    - Empty `steps` returns `initial` unchanged.
    """
    raise NotImplementedError("Complete run_chain — see task.md")
