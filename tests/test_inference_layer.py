from __future__ import annotations

import json
from types import SimpleNamespace

import pytest


class _FakeResp:
    def __init__(self, content: str, prompt_tokens: int = 11, completion_tokens: int = 7):
        self.choices = [SimpleNamespace(message=SimpleNamespace(content=content))]
        self.usage = SimpleNamespace(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens)


class _FakeCompletions:
    def __init__(self):
        self.calls: list[dict] = []
        self._attempt = 0

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        self._attempt += 1
        if self._attempt == 1:
            raise RuntimeError("timeout")
        return _FakeResp(json.dumps({"track": "standard_patch", "reason": "test", "urgency_hours": 24, "confidence": "High"}))


class _FakeClient:
    def __init__(self):
        self.chat = SimpleNamespace(completions=_FakeCompletions())


@pytest.mark.asyncio
async def test_acoomplete_json_fallback_chain_works():
    from levels.l3_routing import RoutingDecision
    from vigil.inference import acomplete_json

    client = _FakeClient()
    payload, info = await acomplete_json(
        client=client,
        task="critique",  # gpt-4o -> gpt-4o-mini fallback
        schema_model=RoutingDecision,
        messages=[{"role": "user", "content": "route this"}],
    )

    assert payload["track"] == "standard_patch"
    assert info.fell_back is True
    assert info.attempts == 2
    assert info.prompt_tokens == 11
    assert info.completion_tokens == 7


def test_get_all_policies_contains_known_tasks():
    from vigil.inference import get_all_policies

    tasks = {p.task for p in get_all_policies()}
    assert {"default", "route", "critique", "judge", "plan"} <= tasks
