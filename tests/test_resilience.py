from __future__ import annotations

import asyncio

import pytest

from reliability import r4_resilience as r4


@pytest.mark.asyncio
async def test_retry_succeeds_after_transient_failures_then_stops():
    calls = {"n": 0}

    async def flaky() -> str:
        calls["n"] += 1
        if calls["n"] < 3:
            raise r4.TransientToolError("temporary")
        return "ok"

    result = await r4.with_retry(flaky, max_attempts=3, base_delay_s=0.0, jitter_s=0.0)
    assert result == "ok"
    assert calls["n"] == 3


@pytest.mark.asyncio
async def test_non_transient_errors_are_not_retried():
    calls = {"n": 0}

    async def bad_request() -> str:
        calls["n"] += 1
        raise r4.NonTransientToolError("400")

    with pytest.raises(r4.NonTransientToolError):
        await r4.with_retry(
            bad_request,
            max_attempts=4,
            base_delay_s=0.0,
            jitter_s=0.0,
            retry_on=(r4.TransientToolError, TimeoutError),
        )
    assert calls["n"] == 1


@pytest.mark.asyncio
async def test_timeout_aborts_slow_call_within_deadline():
    async def slow() -> str:
        await asyncio.sleep(0.05)
        return "late"

    with pytest.raises(TimeoutError):
        await r4.with_timeout(slow, timeout_s=0.01)


@pytest.mark.asyncio
async def test_circuit_breaker_opens_and_short_circuits_calls():
    breaker = r4.CircuitBreaker("test", failure_threshold=2, recovery_timeout_s=60.0)

    async def fail() -> str:
        raise r4.TransientToolError("boom")

    with pytest.raises(r4.TransientToolError):
        await breaker.call(fail)
    with pytest.raises(r4.TransientToolError):
        await breaker.call(fail)

    assert breaker.state == "open"

    with pytest.raises(r4.CircuitOpenError):
        await breaker.call(fail)


@pytest.mark.asyncio
async def test_failed_source_yields_degraded_verdict_not_crash(monkeypatch: pytest.MonkeyPatch):
    async def ok_nvd(_: str) -> str:
        return '{"source":"NVD","severity":"HIGH"}'

    async def fail_epss(_: str) -> str:
        return '{"error":"EPSS API returned 500"}'

    async def ok_kev(_: str) -> str:
        return '{"source":"CISA KEV","in_kev":true}'

    monkeypatch.setitem(r4.TOOL_MAP, "nvd", ok_nvd)
    monkeypatch.setitem(r4.TOOL_MAP, "epss", fail_epss)
    monkeypatch.setitem(r4.TOOL_MAP, "kev", ok_kev)
    r4.reset_breakers()

    verdict = await r4.analyse_cve("CVE-2021-44228")
    assert verdict.cve_id == "CVE-2021-44228"
    assert "epss" in verdict.degraded_sources
    assert verdict.confidence < 1.0


@pytest.mark.asyncio
async def test_l6_scan_idempotent_under_retry_no_duplicate_writes():
    r4.reset_idempotency_cache()
    calls = {"n": 0}

    async def write_once() -> dict[str, str]:
        calls["n"] += 1
        return {"alert_id": "42", "status": "created"}

    created, result1 = await r4.idempotent_scan_step("scan:CVE-1:2026-06-30", write_once)
    created_again, result2 = await r4.idempotent_scan_step("scan:CVE-1:2026-06-30", write_once)

    assert created is True
    assert created_again is False
    assert calls["n"] == 1
    assert result1 == result2
