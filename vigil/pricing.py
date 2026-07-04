"""Centralized model pricing helpers used by inference and cost-control modules."""

from __future__ import annotations

from typing import Mapping

PRICING_PER_MILLION: Mapping[str, tuple[float, float]] = {
    "gpt-4o-mini": (0.150, 0.600),
    "gpt-4o": (2.500, 10.000),
}


def estimate_cost_usd(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    in_price, out_price = PRICING_PER_MILLION.get(model, PRICING_PER_MILLION["gpt-4o-mini"])
    return ((prompt_tokens * in_price) + (completion_tokens * out_price)) / 1_000_000
