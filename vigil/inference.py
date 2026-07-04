"""Shared model/inference layer with routing, fallback, and optional streaming.

F3 extends this seam with multiple **providers** (hosted OpenAI, local Ollama, or any
OpenAI-compatible endpoint). The same `AsyncOpenAI` SDK talks to all of them — only the
`base_url` changes. Providers declare capability flags so the layer degrades gracefully
(e.g. prompt-coerced JSON when a local model lacks strict `json_schema`).
"""

from __future__ import annotations

import json
import os
import re
import time
from typing import Any

from openai import AsyncOpenAI
from pydantic import BaseModel

from vigil.models import InferenceComparison, InferenceResult, ProviderInfo, RoutePolicy
from vigil.pricing import estimate_cost_usd

DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
LOCAL_MODEL = os.getenv("VIGIL_LOCAL_MODEL", "llama3.1:8b")

# ─── PROVIDER REGISTRY ────────────────────────────────────────────────────────
# Each provider is just an OpenAI-compatible endpoint + a capability profile.
PROVIDER_REGISTRY: dict[str, dict[str, Any]] = {
    "openai": {
        "base_url": None,
        "default_model": DEFAULT_MODEL,
        "supports_tools": True,
        "supports_json_schema": True,
    },
    "ollama": {
        "base_url": os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
        "default_model": LOCAL_MODEL,
        "supports_tools": False,
        "supports_json_schema": False,
    },
    "openai_compatible": {
        "base_url": os.getenv("OPENAI_COMPATIBLE_BASE_URL"),
        "default_model": os.getenv("VIGIL_COMPATIBLE_MODEL", DEFAULT_MODEL),
        "supports_tools": True,
        "supports_json_schema": True,
    },
}


def get_providers() -> list[ProviderInfo]:
    """Describe every configured provider and its capability surface."""
    return [
        ProviderInfo(
            name=name,
            base_url=cfg["base_url"],
            default_model=cfg["default_model"],
            supports_tools=cfg["supports_tools"],
            supports_json_schema=cfg["supports_json_schema"],
        )
        for name, cfg in PROVIDER_REGISTRY.items()
    ]


def make_client(provider: str = "openai", base_url: str | None = None) -> AsyncOpenAI:
    """Build an AsyncOpenAI client pointed at the right provider endpoint.

    Local/compatible endpoints still speak the OpenAI wire format, so the only
    thing that changes is `base_url` (and a throwaway api_key the SDK requires).
    """
    cfg = PROVIDER_REGISTRY.get(provider, PROVIDER_REGISTRY["openai"])
    url = base_url or cfg["base_url"]
    if provider == "openai":
        return AsyncOpenAI()
    if provider == "ollama":
        return AsyncOpenAI(base_url=url, api_key=os.getenv("OLLAMA_API_KEY", "ollama"))
    # openai_compatible / anything else with an explicit base_url
    return AsyncOpenAI(base_url=url, api_key=os.getenv("OPENAI_COMPATIBLE_API_KEY", "sk-no-auth"))


ROUTE_POLICIES: dict[str, RoutePolicy] = {
    "default": RoutePolicy(task="default", primary=DEFAULT_MODEL, fallbacks=["gpt-4o-mini"]),
    "route": RoutePolicy(task="route", primary="gpt-4o-mini", fallbacks=[DEFAULT_MODEL]),
    "critique": RoutePolicy(task="critique", primary="gpt-4o", fallbacks=["gpt-4o-mini"]),
    "judge": RoutePolicy(task="judge", primary="gpt-4o", fallbacks=["gpt-4o-mini"]),
    "plan": RoutePolicy(task="plan", primary="gpt-4o", fallbacks=["gpt-4o-mini"]),
}


class InferenceError(Exception):
    pass


class TransientInferenceError(InferenceError):
    pass


def get_policy(task: str) -> RoutePolicy:
    return ROUTE_POLICIES.get(task, ROUTE_POLICIES["default"])


def get_all_policies() -> list[RoutePolicy]:
    return list(ROUTE_POLICIES.values())


def _provider_caps(provider: str) -> dict[str, Any]:
    return PROVIDER_REGISTRY.get(provider, PROVIDER_REGISTRY["openai"])


async def acomplete(
    *,
    client: AsyncOpenAI,
    messages: list[dict[str, Any]],
    task: str = "default",
    model_override: str | None = None,
    provider: str | None = None,
    response_format: dict[str, Any] | None = None,
    temperature: float = 0.1,
    max_tokens: int = 1024,
) -> tuple[str, InferenceResult]:
    policy = get_policy(task)
    effective_provider = provider or policy.provider
    caps = _provider_caps(effective_provider)

    # Model chain: explicit override > provider default (non-openai) > policy chain.
    if model_override:
        chain = [model_override]
    elif provider and effective_provider != "openai":
        chain = [caps["default_model"]]
    else:
        chain = [policy.primary, *policy.fallbacks]
    chain = [m for i, m in enumerate(chain) if m and m not in chain[:i]]

    last_err: Exception | None = None
    for i, model in enumerate(chain, start=1):
        try:
            kwargs: dict[str, Any] = {
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
            if response_format is not None:
                kwargs["response_format"] = response_format

            resp = await client.chat.completions.create(**kwargs)
            msg = resp.choices[0].message.content or ""
            pt = (resp.usage.prompt_tokens if resp.usage else 0) or 0
            ct = (resp.usage.completion_tokens if resp.usage else 0) or 0
            cost = 0.0 if effective_provider != "openai" else estimate_cost_usd(model, pt, ct)
            info = InferenceResult(
                model_used=model,
                fell_back=i > 1,
                attempts=i,
                prompt_tokens=pt,
                completion_tokens=ct,
                cost_usd=round(cost, 6),
                provider=effective_provider,
            )
            return msg, info
        except Exception as e:
            last_err = e
            text = str(e).lower()
            if not any(x in text for x in ("rate", "timeout", "tempor", "connection", "429", "500", "502", "503")):
                raise
            continue

    raise InferenceError(f"All models failed in chain: {chain}. Last error: {last_err}")


# ─── JSON OUTPUT (with capability degradation) ────────────────────────────────

def _extract_json(text: str) -> str:
    """Pull a JSON object out of a model reply that may wrap it in prose/fences."""
    fenced = re.search(r"```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```", text, re.DOTALL)
    if fenced:
        return fenced.group(1)
    brace = re.search(r"(\{.*\}|\[.*\])", text, re.DOTALL)
    return brace.group(1) if brace else text


def _coerce_messages(messages: list[dict[str, Any]], schema: dict[str, Any]) -> list[dict[str, Any]]:
    """Append a strict instruction so a non-schema model still returns valid JSON."""
    instruction = (
        "Respond with a SINGLE JSON object that matches this JSON Schema exactly. "
        "Output JSON only — no prose, no markdown fences.\n\n"
        f"JSON Schema:\n{json.dumps(schema)}"
    )
    return [*messages, {"role": "user", "content": instruction}]


async def acomplete_json(
    *,
    client: AsyncOpenAI,
    messages: list[dict[str, Any]],
    schema_model: type[BaseModel],
    task: str = "default",
    model_override: str | None = None,
    provider: str | None = None,
    temperature: float = 0.1,
    max_tokens: int = 1024,
) -> tuple[dict[str, Any], InferenceResult]:
    schema = schema_model.model_json_schema()
    if "properties" in schema:
        schema["required"] = list(schema["properties"].keys())

    policy = get_policy(task)
    effective_provider = provider or policy.provider
    caps = _provider_caps(effective_provider)

    if caps["supports_json_schema"]:
        content, info = await acomplete(
            client=client,
            messages=messages,
            task=task,
            model_override=model_override,
            provider=provider,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": schema_model.__name__,
                    "strict": True,
                    "schema": schema,
                },
            },
            temperature=temperature,
            max_tokens=max_tokens,
        )
        info.json_mode = "json_schema"
        return json.loads(content), info

    # Degraded path: the model can't enforce a schema, so we instruct + parse.
    content, info = await acomplete(
        client=client,
        messages=_coerce_messages(messages, schema),
        task=task,
        model_override=model_override,
        provider=provider,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    info.json_mode = "prompt_coerced"
    return json.loads(_extract_json(content)), info


# ─── PROVIDER COMPARISON ──────────────────────────────────────────────────────

async def compare_inference(
    *,
    messages: list[dict[str, Any]],
    task: str = "default",
    providers: list[str] | None = None,
    client_factory=make_client,
    max_tokens: int = 512,
) -> InferenceComparison:
    """Run the same prompt across several providers and tabulate latency/cost/output."""
    providers = providers or ["openai"]
    rows: list[dict[str, Any]] = []
    for prov in providers:
        start = time.perf_counter()
        try:
            client = client_factory(prov)
            content, info = await acomplete(
                client=client,
                messages=messages,
                task=task,
                provider=prov,
                max_tokens=max_tokens,
            )
            rows.append(
                {
                    "provider": prov,
                    "model": info.model_used,
                    "latency_ms": int((time.perf_counter() - start) * 1000),
                    "tokens": info.prompt_tokens + info.completion_tokens,
                    "est_cost_usd": info.cost_usd,
                    "output_preview": (content or "").strip()[:200],
                }
            )
        except Exception as e:
            rows.append(
                {
                    "provider": prov,
                    "model": _provider_caps(prov)["default_model"],
                    "latency_ms": int((time.perf_counter() - start) * 1000),
                    "error": str(e),
                }
            )
    return InferenceComparison(task=task, rows=rows)



async def astream(
    *,
    client: AsyncOpenAI,
    messages: list[dict[str, Any]],
    task: str = "default",
    model_override: str | None = None,
    temperature: float = 0.1,
    max_tokens: int = 1024,
):
    policy = get_policy(task)
    model = model_override or policy.primary
    stream = await client.chat.completions.create(
        model=model,
        messages=messages,
        stream=True,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    async for event in stream:
        choice = event.choices[0] if event.choices else None
        if not choice or not choice.delta:
            continue
        token = choice.delta.content
        if token:
            yield token
