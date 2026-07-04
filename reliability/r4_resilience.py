"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  VIGIL — Reliability R4: Resilience in the Agent Loop                       ║
║                                                                              ║
║  Adds retries, timeouts, circuit breakers, and graceful degradation         ║
║  around external data sources so failures do not crash the agent loop.      ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

from __future__ import annotations

import argparse
import asyncio
import json
import random
import re
import time
from typing import Any, Awaitable, Callable, TypeVar

from rich.console import Console
from rich.table import Table

from reliability import r1_guardrails as r1
from vigil.models import ResilientVerdict, SourceStatus

T = TypeVar("T")

console = Console()

_usage: dict = {"prompt_tokens": 0, "completion_tokens": 0}


def _reset_usage() -> None:
    global _usage
    _usage = {"prompt_tokens": 0, "completion_tokens": 0}


def get_usage() -> dict:
    pt = _usage["prompt_tokens"]
    ct = _usage["completion_tokens"]
    return {
        "prompt_tokens": pt,
        "completion_tokens": ct,
        "total_tokens": pt + ct,
        "estimated_cost_usd": 0.0,
    }


class TransientToolError(Exception):
    pass


class NonTransientToolError(Exception):
    pass


class CircuitOpenError(Exception):
    pass


async def with_timeout(call: Callable[[], Awaitable[T]], timeout_s: float) -> T:
    return await asyncio.wait_for(call(), timeout=timeout_s)


async def with_retry(
    call: Callable[[], Awaitable[T]],
    max_attempts: int = 3,
    base_delay_s: float = 0.05,
    jitter_s: float = 0.02,
    retry_on: tuple[type[Exception], ...] = (TransientToolError, TimeoutError),
) -> T:
    if max_attempts < 1:
        raise ValueError("max_attempts must be >= 1")

    last_error: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            return await call()
        except Exception as e:
            if not isinstance(e, retry_on):
                raise
            last_error = e
            if attempt >= max_attempts:
                break
            delay = (base_delay_s * (2 ** (attempt - 1))) + random.uniform(0.0, jitter_s)
            await asyncio.sleep(delay)

    assert last_error is not None
    raise last_error


class CircuitBreaker:
    def __init__(self, name: str, failure_threshold: int = 3, recovery_timeout_s: float = 5.0):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout_s = recovery_timeout_s
        self._state: str = "closed"
        self._consecutive_failures = 0
        self._opened_at: float | None = None

    @property
    def state(self) -> str:
        if self._state == "open" and self._opened_at is not None:
            if (time.monotonic() - self._opened_at) >= self.recovery_timeout_s:
                self._state = "half_open"
        return self._state

    def _record_success(self) -> None:
        self._consecutive_failures = 0
        self._state = "closed"
        self._opened_at = None

    def _record_failure(self) -> None:
        self._consecutive_failures += 1
        if self._state == "half_open" or self._consecutive_failures >= self.failure_threshold:
            self._state = "open"
            self._opened_at = time.monotonic()

    async def call(self, call: Callable[[], Awaitable[T]]) -> T:
        if self.state == "open":
            raise CircuitOpenError(f"circuit is open for {self.name}")

        try:
            result = await call()
            self._record_success()
            return result
        except Exception:
            self._record_failure()
            raise


def parse_chaos(value: str) -> dict[str, str]:
    if not value.strip():
        return {}

    parsed: dict[str, str] = {}
    for part in value.split(","):
        item = part.strip()
        if not item:
            continue
        if "=" not in item:
            raise ValueError(f"Invalid chaos directive: {item}")
        key, mode = item.split("=", 1)
        parsed[key.strip().lower()] = mode.strip().lower()
    return parsed


_CHAOS_COUNTERS: dict[str, int] = {}


async def _apply_chaos(source: str, mode: str | None) -> None:
    if not mode:
        return

    if mode == "timeout":
        await asyncio.sleep(0.2)
        raise TimeoutError(f"forced timeout for {source}")
    if mode in {"500", "transient"}:
        raise TransientToolError(f"forced transient failure for {source}")
    if mode in {"400", "permanent"}:
        raise NonTransientToolError(f"forced non-transient failure for {source}")
    if mode == "flaky":
        count = _CHAOS_COUNTERS.get(source, 0)
        _CHAOS_COUNTERS[source] = count + 1
        if count % 2 == 0:
            raise TransientToolError(f"forced flaky failure for {source}")


TOOL_MAP: dict[str, Callable[[str], Awaitable[str]]] = {
    "nvd": r1.fetch_nvd_data,
    "epss": r1.fetch_epss_score,
    "kev": r1.check_cisa_kev,
}

_BREAKERS: dict[str, CircuitBreaker] = {
    "nvd": CircuitBreaker("nvd", failure_threshold=2, recovery_timeout_s=2.0),
    "epss": CircuitBreaker("epss", failure_threshold=2, recovery_timeout_s=2.0),
    "kev": CircuitBreaker("kev", failure_threshold=2, recovery_timeout_s=2.0),
}


def _is_non_transient_payload_error(payload: dict[str, Any]) -> bool:
    err = str(payload.get("error", ""))
    return bool(re.search(r"\b400\b", err))


def get_circuit_states() -> dict[str, str]:
    return {name: cb.state for name, cb in _BREAKERS.items()}


def reset_breakers() -> None:
    global _BREAKERS
    _BREAKERS = {
        "nvd": CircuitBreaker("nvd", failure_threshold=2, recovery_timeout_s=2.0),
        "epss": CircuitBreaker("epss", failure_threshold=2, recovery_timeout_s=2.0),
        "kev": CircuitBreaker("kev", failure_threshold=2, recovery_timeout_s=2.0),
    }


_IDEMPOTENT_RESULTS: dict[str, dict[str, Any]] = {}


async def idempotent_scan_step(key: str, action: Callable[[], Awaitable[dict[str, Any]]]) -> tuple[bool, dict[str, Any]]:
    if key in _IDEMPOTENT_RESULTS:
        return False, _IDEMPOTENT_RESULTS[key]

    result = await action()
    _IDEMPOTENT_RESULTS[key] = result
    return True, result


def reset_idempotency_cache() -> None:
    _IDEMPOTENT_RESULTS.clear()


async def _call_source(source: str, cve_id: str, chaos_mode: str | None) -> tuple[dict[str, Any], SourceStatus]:
    breaker = _BREAKERS[source]
    attempts = 0

    async def attempt_call() -> dict[str, Any]:
        nonlocal attempts
        attempts += 1

        await _apply_chaos(source, chaos_mode)
        raw = await TOOL_MAP[source](cve_id)
        payload = json.loads(raw)
        if "error" in payload:
            if _is_non_transient_payload_error(payload):
                raise NonTransientToolError(str(payload["error"]))
            raise TransientToolError(str(payload["error"]))
        return payload

    try:
        payload = await breaker.call(
            lambda: with_retry(
                lambda: with_timeout(attempt_call, timeout_s=0.1),
                max_attempts=3,
                base_delay_s=0.02,
                jitter_s=0.0,
                retry_on=(TransientToolError, TimeoutError),
            )
        )
        status = SourceStatus(name=source, available=True, attempts=attempts, circuit=breaker.state)
        return payload, status
    except CircuitOpenError:
        status = SourceStatus(name=source, available=False, attempts=attempts, circuit=breaker.state)
        return {"error": "circuit open"}, status
    except Exception as e:
        status = SourceStatus(name=source, available=False, attempts=attempts, circuit=breaker.state)
        return {"error": str(e)}, status


async def analyse_cve(cve_id: str, chaos: dict[str, str] | None = None) -> ResilientVerdict:
    _reset_usage()
    chaos = chaos or {}

    nvd_payload, nvd_status = await _call_source("nvd", cve_id, chaos.get("nvd"))
    epss_payload, epss_status = await _call_source("epss", cve_id, chaos.get("epss"))
    kev_payload, kev_status = await _call_source("kev", cve_id, chaos.get("kev"))

    statuses = [nvd_status, epss_status, kev_status]
    degraded_sources = [s.name for s in statuses if not s.available]

    confidence = max(0.0, round(1.0 - (0.2 * len(degraded_sources)), 3))
    summary_parts: list[str] = []

    if nvd_status.available:
        summary_parts.append(f"NVD severity={nvd_payload.get('severity', 'UNKNOWN')}")
    if epss_status.available:
        summary_parts.append(f"EPSS={epss_payload.get('score', 0)}")
    if kev_status.available:
        summary_parts.append(f"KEV={'yes' if kev_payload.get('in_kev') else 'no'}")

    if degraded_sources:
        summary_parts.append(f"Degraded sources: {', '.join(degraded_sources)}")

    return ResilientVerdict(
        cve_id=cve_id,
        confidence=confidence,
        degraded_sources=degraded_sources,
        sources=statuses,
        summary=" | ".join(summary_parts) if summary_parts else "No source data available",
    )


def _display_verdict(verdict: ResilientVerdict) -> None:
    table = Table(title=f"R4 Resilience Verdict — {verdict.cve_id}")
    table.add_column("Source")
    table.add_column("Available")
    table.add_column("Attempts")
    table.add_column("Circuit")

    for s in verdict.sources:
        table.add_row(s.name, "yes" if s.available else "no", str(s.attempts), s.circuit)

    console.print(table)
    console.print(f"Confidence: {verdict.confidence:.2f}")
    console.print(f"Summary: {verdict.summary}")


def main() -> None:
    parser = argparse.ArgumentParser(description="R4 resilience demo")
    parser.add_argument("cve_id", nargs="?", default="CVE-2021-44228")
    parser.add_argument("--chaos", default="", help="e.g. epss=timeout,nvd=500")
    args = parser.parse_args()

    chaos = parse_chaos(args.chaos)
    verdict = asyncio.run(analyse_cve(args.cve_id, chaos=chaos))
    _display_verdict(verdict)


if __name__ == "__main__":
    main()
