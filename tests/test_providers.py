from __future__ import annotations

import json
from types import SimpleNamespace

import pytest


class _FakeResp:
    def __init__(self, content: str, prompt_tokens: int = 10, completion_tokens: int = 5):
        self.choices = [SimpleNamespace(message=SimpleNamespace(content=content))]
        self.usage = SimpleNamespace(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens)


class _FakeCompletions:
    def __init__(self, content: str):
        self.calls: list[dict] = []
        self._content = content

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        return _FakeResp(self._content)


class _FakeClient:
    def __init__(self, content: str):
        self.chat = SimpleNamespace(completions=_FakeCompletions(content))


def test_get_providers_lists_openai_and_ollama():
    from vigil.inference import get_providers

    providers = {p.name: p for p in get_providers()}
    assert {"openai", "ollama", "openai_compatible"} <= set(providers)

    # OpenAI supports strict schema; Ollama (local) does not by default.
    assert providers["openai"].supports_json_schema is True
    assert providers["ollama"].supports_json_schema is False
    assert providers["ollama"].base_url is not None


def test_make_client_ollama_uses_base_url(monkeypatch):
    captured: dict = {}

    class _Stub:
        def __init__(self, *args, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr("vigil.inference.AsyncOpenAI", _Stub)
    from vigil.inference import make_client

    make_client("ollama")
    assert "11434" in captured["base_url"]
    assert captured.get("api_key")  # SDK requires a key even for local


@pytest.mark.asyncio
async def test_local_model_uses_prompt_coerced_json():
    from levels.l3_routing import RoutingDecision
    from vigil.inference import acomplete_json

    # A local model can't enforce json_schema, so it returns JSON wrapped in fences.
    fenced = "```json\n" + json.dumps(
        {"track": "standard_patch", "reason": "local", "urgency_hours": 24, "confidence": "High"}
    ) + "\n```"
    client = _FakeClient(fenced)

    payload, info = await acomplete_json(
        client=client,
        provider="ollama",
        schema_model=RoutingDecision,
        messages=[{"role": "user", "content": "route this"}],
    )

    assert payload["track"] == "standard_patch"
    assert info.json_mode == "prompt_coerced"
    assert info.provider == "ollama"
    # No response_format was sent — the model can't honour it.
    assert "response_format" not in client.chat.completions.calls[0]


@pytest.mark.asyncio
async def test_openai_provider_uses_strict_schema():
    from levels.l3_routing import RoutingDecision
    from vigil.inference import acomplete_json

    payload_json = json.dumps(
        {"track": "standard_patch", "reason": "hosted", "urgency_hours": 12, "confidence": "High"}
    )
    client = _FakeClient(payload_json)

    payload, info = await acomplete_json(
        client=client,
        provider="openai",
        schema_model=RoutingDecision,
        messages=[{"role": "user", "content": "route this"}],
    )

    assert payload["track"] == "standard_patch"
    assert info.json_mode == "json_schema"
    assert client.chat.completions.calls[0]["response_format"]["type"] == "json_schema"


@pytest.mark.asyncio
async def test_compare_inference_aggregates_rows():
    from vigil.inference import compare_inference

    def factory(provider: str):
        return _FakeClient(f"summary from {provider}")

    comparison = await compare_inference(
        messages=[{"role": "user", "content": "summarise"}],
        providers=["openai", "ollama"],
        client_factory=factory,
    )

    assert comparison.task == "default"
    assert {r["provider"] for r in comparison.rows} == {"openai", "ollama"}
    for row in comparison.rows:
        assert "latency_ms" in row
        assert "output_preview" in row
    # Local provider is billed at $0.
    ollama_row = next(r for r in comparison.rows if r["provider"] == "ollama")
    assert ollama_row["est_cost_usd"] == 0.0


@pytest.mark.asyncio
async def test_compare_inference_records_provider_error():
    from vigil.inference import compare_inference

    def factory(provider: str):
        if provider == "ollama":
            raise ConnectionError("ollama not running")
        return _FakeClient("hosted summary")

    comparison = await compare_inference(
        messages=[{"role": "user", "content": "summarise"}],
        providers=["openai", "ollama"],
        client_factory=factory,
    )

    ollama_row = next(r for r in comparison.rows if r["provider"] == "ollama")
    assert "error" in ollama_row
    openai_row = next(r for r in comparison.rows if r["provider"] == "openai")
    assert "error" not in openai_row
