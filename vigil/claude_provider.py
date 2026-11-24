"""
Claude Messages API bridge (additive, optional).

This module does NOT change the existing OpenAI-based inference seam. It provides
an isolated path so learners can run against the Anthropic Messages API and study
Claude-specific concepts (system parameter, tool-use blocks, stop reasons).

The message-mapping logic is pure and offline-testable. Actual network calls lazily
import the `anthropic` package and fail with a clear message if it is absent.
"""

from __future__ import annotations

import os
from typing import Any

DEFAULT_CLAUDE_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5")


def map_messages_to_claude(messages: list[dict[str, Any]]) -> dict[str, Any]:
    """Convert OpenAI-style chat messages into Claude Messages API shape.

    Claude takes the system prompt as a top-level `system` parameter, not a role.
    Returns a dict with `system` (str) and `messages` (user/assistant only).
    """
    system_parts: list[str] = []
    claude_messages: list[dict[str, Any]] = []

    for m in messages:
        role = m.get("role")
        content = m.get("content", "")
        if role == "system":
            if content:
                system_parts.append(str(content))
        elif role in ("user", "assistant"):
            claude_messages.append(
                {
                    "role": role,
                    "content": [{"type": "text", "text": str(content)}],
                }
            )
        # tool/function roles are intentionally ignored in this teaching bridge.

    return {
        "system": "\n\n".join(system_parts).strip(),
        "messages": claude_messages,
    }


def map_tools_to_claude(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert simple tool descriptors into Claude tool definitions."""
    out: list[dict[str, Any]] = []
    for t in tools:
        out.append(
            {
                "name": t.get("name", "tool"),
                "description": t.get("description", ""),
                "input_schema": t.get("input_schema", {"type": "object", "properties": {}}),
            }
        )
    return out


def anthropic_available() -> bool:
    try:
        import anthropic  # noqa: F401

        return True
    except Exception:
        return False


async def acomplete_claude(
    *,
    messages: list[dict[str, Any]],
    model: str | None = None,
    temperature: float = 0.1,
    max_tokens: int = 1024,
) -> dict[str, Any]:
    """Complete via the Anthropic Messages API. Requires the `anthropic` extra."""
    try:
        from anthropic import AsyncAnthropic
    except Exception as exc:  # pragma: no cover - exercised only without extra
        raise RuntimeError(
            "The 'anthropic' package is required. Install with: pip install -e .[claude]"
        ) from exc

    mapped = map_messages_to_claude(messages)
    client = AsyncAnthropic()
    resp = await client.messages.create(
        model=model or DEFAULT_CLAUDE_MODEL,
        system=mapped["system"] or None,
        messages=mapped["messages"],
        temperature=temperature,
        max_tokens=max_tokens,
    )

    text = "".join(
        block.text for block in resp.content if getattr(block, "type", None) == "text"
    )
    return {
        "text": text,
        "model": resp.model,
        "stop_reason": resp.stop_reason,
        "input_tokens": resp.usage.input_tokens,
        "output_tokens": resp.usage.output_tokens,
    }
