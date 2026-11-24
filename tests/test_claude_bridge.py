from __future__ import annotations

import pytest

from vigil.claude_provider import map_messages_to_claude, map_tools_to_claude


def test_system_message_becomes_top_level_system():
    mapped = map_messages_to_claude(
        [
            {"role": "system", "content": "You are a CVE analyst."},
            {"role": "user", "content": "Summarize CVE-2021-44228."},
        ]
    )
    assert mapped["system"] == "You are a CVE analyst."
    assert len(mapped["messages"]) == 1
    assert mapped["messages"][0]["role"] == "user"
    assert mapped["messages"][0]["content"][0]["type"] == "text"


def test_multiple_system_messages_are_joined():
    mapped = map_messages_to_claude(
        [
            {"role": "system", "content": "Rule A."},
            {"role": "system", "content": "Rule B."},
            {"role": "user", "content": "Hi"},
        ]
    )
    assert "Rule A." in mapped["system"]
    assert "Rule B." in mapped["system"]


def test_map_tools_to_claude_shape():
    tools = [{"name": "fetch_nvd_data", "description": "d", "input_schema": {"type": "object"}}]
    out = map_tools_to_claude(tools)
    assert out[0]["name"] == "fetch_nvd_data"
    assert "input_schema" in out[0]


@pytest.mark.asyncio
async def test_mcp_tool_loop_offline_with_injected_invoker():
    from vigil_mcp.vigil_client import run_tool_loop

    async def fake_invoker(name, args):
        return {"tool": name, "cve_id": args.get("cve_id"), "ok": True}

    out = await run_tool_loop(cve_id="CVE-2021-44228", invoker=fake_invoker)
    assert out["tool_calls"] == 2
    assert out["transcript"][0]["result"]["ok"] is True
    assert out["stop_reason"] == "end_turn"
