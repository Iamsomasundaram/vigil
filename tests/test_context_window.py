from __future__ import annotations

from datetime import datetime, timezone

import pytest


def _entry(i: int) -> dict:
    """Build a fake history row in the shape the context builder expects."""
    return {
        "created_at": datetime(2024, 1, 1 + (i % 27), 12, 0, tzinfo=timezone.utc),
        "result": {
            "cvss_score": 9.8,
            "cvss_severity": "CRITICAL",
            "epss_score": 0.5 + i / 1000,
            "patch_available": i % 2 == 0,
            "recommended_action": f"REC-{i}-patch-immediately-and-monitor-exploitation-trends",
        },
        "feedback_status": "patched" if i % 3 == 0 else None,
        "feedback_notes": f"note-{i}" if i % 3 == 0 else None,
    }


async def _fake_summarizer(entries: list[dict]) -> str:
    return "- severity stable\n- EPSS trending up"


def test_count_tokens_is_positive():
    from levels.l5_memory import count_tokens

    assert count_tokens("hello world") >= 1
    assert count_tokens("") == 1 or count_tokens("") == 0  # heuristic floors at 1


@pytest.mark.asyncio
async def test_small_history_fits_verbatim():
    from levels.l5_memory import build_budgeted_memory_context

    history = [_entry(0), _entry(1)]
    text, report = await build_budgeted_memory_context(
        history, max_tokens=2000, recent_k=2, summarizer=_fake_summarizer
    )

    assert report.was_truncated is False
    assert report.was_summarized is False
    assert report.entries_verbatim == 2
    assert report.entries_summarized == 0
    assert report.used_tokens <= report.budget_tokens
    # All recommendations present verbatim.
    assert "REC-0-" in text and "REC-1-" in text


@pytest.mark.asyncio
async def test_over_budget_triggers_summarization_keeps_recent_verbatim():
    from levels.l5_memory import build_budgeted_memory_context, count_tokens

    history = [_entry(i) for i in range(12)]  # newest-first by convention
    text, report = await build_budgeted_memory_context(
        history, max_tokens=120, recent_k=1, summarizer=_fake_summarizer
    )

    assert report.was_summarized is True
    assert report.was_truncated is False
    assert report.entries_verbatim == 1
    assert report.entries_summarized == 11
    # Hard budget is never exceeded.
    assert report.used_tokens <= report.budget_tokens
    assert count_tokens(text) <= report.budget_tokens
    # The single most-recent entry is kept verbatim; the summary digest is present.
    assert "REC-0-" in text
    assert "summarized" in text.lower()


@pytest.mark.asyncio
async def test_summarizer_failure_falls_back_to_truncation_within_budget():
    from levels.l5_memory import build_budgeted_memory_context

    async def _boom(entries: list[dict]) -> str:
        raise RuntimeError("summarizer offline")

    history = [_entry(i) for i in range(10)]
    text, report = await build_budgeted_memory_context(
        history, max_tokens=70, recent_k=3, summarizer=_boom
    )

    assert report.was_summarized is False
    assert report.was_truncated is True
    # Even when summarization fails, the budget is still respected.
    assert report.used_tokens <= report.budget_tokens


@pytest.mark.asyncio
async def test_empty_history_reports_zero_entries():
    from levels.l5_memory import build_budgeted_memory_context

    text, report = await build_budgeted_memory_context([], max_tokens=500)

    assert report.entries_verbatim == 0
    assert report.entries_summarized == 0
    assert report.was_truncated is False
    assert report.was_summarized is False
    assert "No prior analyses" in text
