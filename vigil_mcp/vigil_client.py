"""
MCP client path (additive).

A minimal in-process MCP client that discovers and invokes tools exposed by
`vigil_mcp.vigil_server`. It also runs a Claude-style tool-use loop so learners can see
how a client drives tool calls to completion. No changes to existing L4 behavior.
"""

from __future__ import annotations

import json
from typing import Any, Awaitable, Callable

from vigil_mcp.vigil_server import call_tool, list_tools


async def discover() -> list[dict[str, Any]]:
    """Discover tool definitions from the MCP server."""
    return list_tools()


async def invoke(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Invoke a tool by name via the MCP server and parse its JSON result."""
    raw = await call_tool(name, arguments)
    try:
        return json.loads(raw)
    except Exception:
        return {"raw": raw}


async def run_tool_loop(
    *,
    cve_id: str,
    plan: list[dict[str, Any]] | None = None,
    invoker: Callable[[str, dict[str, Any]], Awaitable[dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    """Run a deterministic Claude-style tool loop over the MCP tools.

    ``plan`` lists the tool calls to make; defaults to NVD then EPSS. ``invoker``
    is injectable so tests can run fully offline without network access.
    """
    call = invoker or invoke
    steps = plan or [
        {"tool": "fetch_nvd_data", "arguments": {"cve_id": cve_id}},
        {"tool": "fetch_epss_score", "arguments": {"cve_id": cve_id}},
    ]

    transcript: list[dict[str, Any]] = []
    for step in steps:
        tool = step["tool"]
        args = step.get("arguments", {})
        result = await call(tool, args)
        transcript.append({"tool": tool, "arguments": args, "result": result})

    return {
        "cve_id": cve_id,
        "tool_calls": len(transcript),
        "transcript": transcript,
        "stop_reason": "end_turn",
    }
