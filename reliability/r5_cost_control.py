"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  VIGIL — Reliability R5: Cost Control & Token Economics                     ║
║                                                                              ║
║  Adds budget guards, response caching, cost attribution, and context         ║
║  fitting so agent costs are controlled instead of merely observed.           ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from rich.console import Console
from rich.table import Table

from vigil.models import BudgetStatus, CostEntry, CostReport

console = Console()
MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# USD per 1M tokens (simplified table for the learning project)
PRICING_PER_MILLION: dict[str, tuple[float, float]] = {
    "gpt-4o-mini": (0.150, 0.600),
    "gpt-4o": (2.500, 10.000),
}


def estimate_cost_usd(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    in_price, out_price = PRICING_PER_MILLION.get(model, PRICING_PER_MILLION["gpt-4o-mini"])
    return ((prompt_tokens * in_price) + (completion_tokens * out_price)) / 1_000_000


def estimate_tokens_from_messages(messages: list[dict[str, str]]) -> int:
    text = " ".join(m.get("content", "") for m in messages)
    return max(1, len(text) // 4)


def fit_context(messages: list[dict[str, str]], token_ceiling: int) -> list[dict[str, str]]:
    if token_ceiling <= 0:
        return []

    if estimate_tokens_from_messages(messages) <= token_ceiling:
        return messages

    fitted = list(messages)
    while fitted and estimate_tokens_from_messages(fitted) > token_ceiling:
        drop_index = 1 if len(fitted) > 1 else 0
        fitted.pop(drop_index)
    return fitted


class BudgetExceededError(Exception):
    pass


@dataclass
class BudgetGuard:
    request_cap_usd: float = 0.010
    session_cap_usd: float = 1.000
    warn_ratio: float = 0.80
    session_spent_usd: float = 0.0

    def set_caps(self, request_cap_usd: float, session_cap_usd: float, warn_ratio: float) -> None:
        self.request_cap_usd = max(0.0, request_cap_usd)
        self.session_cap_usd = max(0.0, session_cap_usd)
        self.warn_ratio = min(1.0, max(0.0, warn_ratio))

    def check_estimate(self, estimated_cost_usd: float) -> tuple[bool, bool, str | None]:
        if estimated_cost_usd > self.request_cap_usd:
            return False, False, "request_cap_exceeded"
        if (self.session_spent_usd + estimated_cost_usd) > self.session_cap_usd:
            return False, False, "session_cap_exceeded"

        warn_trigger = self.session_cap_usd * self.warn_ratio
        warn = (self.session_spent_usd + estimated_cost_usd) >= warn_trigger
        return True, warn, None

    def consume(self, cost_usd: float) -> BudgetStatus:
        self.session_spent_usd += max(0.0, cost_usd)
        remaining = max(0.0, self.session_cap_usd - self.session_spent_usd)
        return BudgetStatus(
            limit_usd=self.session_cap_usd,
            spent_usd=round(self.session_spent_usd, 6),
            remaining_usd=round(remaining, 6),
            exceeded=self.session_spent_usd > self.session_cap_usd,
        )

    def status(self) -> BudgetStatus:
        remaining = max(0.0, self.session_cap_usd - self.session_spent_usd)
        return BudgetStatus(
            limit_usd=self.session_cap_usd,
            spent_usd=round(self.session_spent_usd, 6),
            remaining_usd=round(remaining, 6),
            exceeded=self.session_spent_usd > self.session_cap_usd,
        )


class ResponseCache:
    def __init__(self):
        self._store: dict[str, dict[str, Any]] = {}

    @staticmethod
    def key_for(model: str, system: str, user: str, tools: list[str] | None = None) -> str:
        payload = {
            "model": model,
            "system": system,
            "user": user,
            "tools": tools or [],
        }
        raw = json.dumps(payload, sort_keys=True, ensure_ascii=True)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def get(self, key: str) -> dict[str, Any] | None:
        return self._store.get(key)

    def put(self, key: str, value: dict[str, Any]) -> None:
        self._store[key] = value


class CostLedger:
    def __init__(self):
        self._entries: list[CostEntry] = []

    def record(self, entry: CostEntry) -> None:
        self._entries.append(entry)

    def entries(self) -> list[CostEntry]:
        return list(self._entries)

    def clear(self) -> None:
        self._entries.clear()

    def report(self) -> CostReport:
        by_feature: dict[str, float] = {}
        by_model: dict[str, float] = {}
        total = 0.0
        cache_savings = 0.0

        for e in self._entries:
            total += e.cost_usd
            by_feature[e.feature] = by_feature.get(e.feature, 0.0) + e.cost_usd
            by_model[e.model] = by_model.get(e.model, 0.0) + e.cost_usd

            if e.cache_hit:
                cache_savings += estimate_cost_usd(e.model, e.prompt_tokens, e.completion_tokens)

        return CostReport(
            entries=self.entries(),
            total_usd=round(total, 6),
            by_feature={k: round(v, 6) for k, v in by_feature.items()},
            by_model={k: round(v, 6) for k, v in by_model.items()},
            cache_savings_usd=round(cache_savings, 6),
        )


_BUDGET = BudgetGuard()
_CACHE = ResponseCache()
_LEDGER = CostLedger()


def set_budget(request_cap_usd: float, session_cap_usd: float, warn_ratio: float) -> BudgetStatus:
    _BUDGET.set_caps(request_cap_usd, session_cap_usd, warn_ratio)
    return _BUDGET.status()


def get_budget_status() -> BudgetStatus:
    return _BUDGET.status()


def get_cost_report() -> CostReport:
    return _LEDGER.report()


def reset_state() -> None:
    _LEDGER.clear()
    _CACHE._store.clear()
    _BUDGET.session_spent_usd = 0.0


async def execute_with_cost_control(
    *,
    feature: str,
    cve_id: str | None,
    model: str,
    system_prompt: str,
    user_prompt: str,
    tools: list[str] | None,
    call_fn: Callable[[list[dict[str, str]]], Awaitable[dict[str, Any]]],
    context_token_ceiling: int = 4000,
) -> dict[str, Any]:
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    messages = fit_context(messages, token_ceiling=context_token_ceiling)

    key = _CACHE.key_for(model, messages[0]["content"], messages[-1]["content"], tools=tools)
    cached = _CACHE.get(key)
    if cached is not None:
        _LEDGER.record(
            CostEntry(
                feature=feature,
                cve_id=cve_id,
                model=model,
                prompt_tokens=int(cached.get("prompt_tokens", 0)),
                completion_tokens=int(cached.get("completion_tokens", 0)),
                cost_usd=0.0,
                cache_hit=True,
            )
        )
        return {
            "result": cached.get("result"),
            "cache_hit": True,
            "budget_status": _BUDGET.status(),
            "warn": False,
        }

    estimated_prompt_tokens = estimate_tokens_from_messages(messages)
    estimated_completion_tokens = 300
    estimated_cost = estimate_cost_usd(model, estimated_prompt_tokens, estimated_completion_tokens)
    allowed, warn, reason = _BUDGET.check_estimate(estimated_cost)
    if not allowed:
        raise BudgetExceededError(reason or "budget_exceeded")

    payload = await call_fn(messages)
    prompt_tokens = int(payload.get("prompt_tokens", estimated_prompt_tokens))
    completion_tokens = int(payload.get("completion_tokens", 0))
    cost_usd = estimate_cost_usd(model, prompt_tokens, completion_tokens)

    _LEDGER.record(
        CostEntry(
            feature=feature,
            cve_id=cve_id,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost_usd=round(cost_usd, 6),
            cache_hit=False,
        )
    )
    budget_status = _BUDGET.consume(cost_usd)

    _CACHE.put(
        key,
        {
            "result": payload.get("result"),
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
        },
    )

    return {
        "result": payload.get("result"),
        "cache_hit": False,
        "budget_status": budget_status.model_dump(),
        "warn": warn,
    }


async def demo_analyse(cve_id: str) -> dict[str, Any]:
    async def fake_llm(messages: list[dict[str, str]]) -> dict[str, Any]:
        text = " ".join(m.get("content", "") for m in messages)
        return {
            "result": {
                "summary": f"Cost-controlled analysis for {cve_id}",
                "chars_seen": len(text),
            },
            "prompt_tokens": estimate_tokens_from_messages(messages),
            "completion_tokens": 140,
        }

    return await execute_with_cost_control(
        feature="r5",
        cve_id=cve_id,
        model=MODEL,
        system_prompt="You are a cost-aware security assistant.",
        user_prompt=f"Analyse {cve_id} and provide a concise remediation summary.",
        tools=[],
        call_fn=fake_llm,
    )


def render_report(report: CostReport) -> None:
    table = Table(title="R5 Cost Report")
    table.add_column("Feature")
    table.add_column("Model")
    table.add_column("Prompt")
    table.add_column("Completion")
    table.add_column("Cost USD")
    table.add_column("Cache")

    for e in report.entries:
        table.add_row(
            e.feature,
            e.model,
            str(e.prompt_tokens),
            str(e.completion_tokens),
            f"{e.cost_usd:.6f}",
            "hit" if e.cache_hit else "miss",
        )

    console.print(table)
    console.print(f"Total: ${report.total_usd:.6f}")
    console.print(f"Cache savings: ${report.cache_savings_usd:.6f}")


def main() -> None:
    parser = argparse.ArgumentParser(description="R5 cost control demo")
    parser.add_argument("cve_id", nargs="?", default="CVE-2021-44228")
    parser.add_argument("--budget", type=float, default=0.010)
    parser.add_argument("--report", action="store_true")
    args = parser.parse_args()

    set_budget(request_cap_usd=args.budget, session_cap_usd=max(args.budget * 20, 0.1), warn_ratio=0.8)
    if args.report:
        render_report(get_cost_report())
        return

    try:
        payload = asyncio.run(demo_analyse(args.cve_id))
        console.print(json.dumps(payload, indent=2))
    except BudgetExceededError as e:
        console.print(json.dumps({"halted": True, "reason": str(e), "budget_status": get_budget_status().model_dump()}, indent=2))


if __name__ == "__main__":
    main()
