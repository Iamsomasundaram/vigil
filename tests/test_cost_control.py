from __future__ import annotations

import pytest

from reliability import r5_cost_control as r5


def test_budget_guard_halts_and_warns_at_threshold():
    guard = r5.BudgetGuard(request_cap_usd=0.001, session_cap_usd=0.01, warn_ratio=0.5)

    allowed, warn, reason = guard.check_estimate(0.0001)
    assert allowed is True
    assert warn is False
    assert reason is None

    guard.consume(0.0049)
    allowed2, warn2, reason2 = guard.check_estimate(0.0002)
    assert allowed2 is True
    assert warn2 is True
    assert reason2 is None

    allowed3, warn3, reason3 = guard.check_estimate(0.002)
    assert allowed3 is False
    assert warn3 is False
    assert reason3 == "request_cap_exceeded"


@pytest.mark.asyncio
async def test_identical_request_hits_cache_and_costs_zero():
    r5.reset_state()
    r5.set_budget(0.05, 0.5, 0.8)

    async def fake_call(_messages):
        return {
            "result": {"ok": True},
            "prompt_tokens": 100,
            "completion_tokens": 50,
        }

    first = await r5.execute_with_cost_control(
        feature="l2",
        cve_id="CVE-2021-44228",
        model="gpt-4o-mini",
        system_prompt="sys",
        user_prompt="usr",
        tools=["nvd"],
        call_fn=fake_call,
    )
    second = await r5.execute_with_cost_control(
        feature="l2",
        cve_id="CVE-2021-44228",
        model="gpt-4o-mini",
        system_prompt="sys",
        user_prompt="usr",
        tools=["nvd"],
        call_fn=fake_call,
    )

    assert first["cache_hit"] is False
    assert second["cache_hit"] is True

    report = r5.get_cost_report()
    assert len(report.entries) == 2
    assert report.entries[1].cache_hit is True
    assert report.entries[1].cost_usd == 0.0


@pytest.mark.asyncio
async def test_attribution_groups_by_feature_and_model_and_cache_savings():
    r5.reset_state()
    r5.set_budget(0.1, 1.0, 0.8)

    async def fake_call(_messages):
        return {
            "result": {"ok": True},
            "prompt_tokens": 120,
            "completion_tokens": 80,
        }

    await r5.execute_with_cost_control(
        feature="r1",
        cve_id="CVE-1",
        model="gpt-4o-mini",
        system_prompt="s1",
        user_prompt="u1",
        tools=[],
        call_fn=fake_call,
    )
    await r5.execute_with_cost_control(
        feature="r2",
        cve_id="CVE-2",
        model="gpt-4o-mini",
        system_prompt="s2",
        user_prompt="u2",
        tools=[],
        call_fn=fake_call,
    )
    await r5.execute_with_cost_control(
        feature="r2",
        cve_id="CVE-2",
        model="gpt-4o-mini",
        system_prompt="s2",
        user_prompt="u2",
        tools=[],
        call_fn=fake_call,
    )

    report = r5.get_cost_report()
    assert report.by_feature["r1"] > 0.0
    assert report.by_feature["r2"] > 0.0
    assert report.by_model["gpt-4o-mini"] > 0.0
    assert report.cache_savings_usd > 0.0


def test_fit_context_trims_below_ceiling():
    messages = [
        {"role": "system", "content": "A" * 2000},
        {"role": "user", "content": "B" * 2000},
        {"role": "assistant", "content": "C" * 2000},
    ]

    fitted = r5.fit_context(messages, token_ceiling=600)
    assert r5.estimate_tokens_from_messages(fitted) <= 600
    assert len(fitted) < len(messages)
