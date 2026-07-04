"""Exercise L0 — Constructing a prompt.

Implement `build_analysis_messages` so the grader passes.
See task.md for the full description.
"""

from __future__ import annotations


def build_analysis_messages(cve_id: str, system_role: str) -> list[dict]:
    """Return a [system, user] message list for analysing `cve_id`.

    Requirements:
      - Exactly two messages.
      - messages[0] == {"role": "system",  "content": system_role}
      - messages[1] is a user message whose content mentions cve_id.
    """
    raise NotImplementedError("Complete build_analysis_messages — see task.md")
