"""Centralized model pricing and context-budget helpers."""

from __future__ import annotations

from typing import Mapping

# INDICATIVE ONLY: USD per million tokens (input, output) as of when this was written.
# Provider prices change and are not synced here; use for rough estimates, not billing.
PRICING_PER_MILLION: Mapping[str, tuple[float, float]] = {
    "gpt-4o-mini": (0.150, 0.600),
    "gpt-4o": (2.500, 10.000),
}

CONTEXT_LIMITS: Mapping[str, int] = {
    "gpt-4o-mini": 128_000,
    "gpt-4o": 128_000,
}


def estimate_cost_usd(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    in_price, out_price = PRICING_PER_MILLION.get(model, PRICING_PER_MILLION["gpt-4o-mini"])
    return ((prompt_tokens * in_price) + (completion_tokens * out_price)) / 1_000_000


def context_limit_for_model(model: str) -> int:
    return CONTEXT_LIMITS.get(model, CONTEXT_LIMITS["gpt-4o-mini"])


def budget_report(model: str, prompt_tokens: int, completion_tokens: int = 0) -> dict:
    """Summarize prompt size vs context limit and projected token cost."""
    limit = context_limit_for_model(model)
    used = max(0, int(prompt_tokens))
    return {
        "model": model,
        "prompt_tokens": used,
        "completion_tokens": max(0, int(completion_tokens)),
        "context_limit": limit,
        "pct_of_context": round((used / limit) * 100, 4) if limit else 0.0,
        "over_limit": used > limit,
        "estimated_cost_usd": round(estimate_cost_usd(model, used, max(0, int(completion_tokens))), 6),
    }
