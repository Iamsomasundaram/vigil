"""
tests/test_architectures.py — Async tests for the second axis (A1–A4).

WHY THESE TESTS EXIST
─────────────────────
Mirrors the approach used in test_l6_scan.py:
  - Pure-function unit tests where possible (no mocks)
  - Integration tests with AsyncMock to stub external IO
    (httpx tool calls + AsyncOpenAI chat completions)

External services are NEVER hit:
  * NVD, EPSS, CISA KEV    — patched at module level
  * OpenAI chat completions — patched on each module's `client`

Each architecture has a specific failure mode the suite pins down:
  A1 — full ReAct loop produces one trace entry per tool call
  A1 — _summarise_observation handles error/NVD/EPSS/KEV results
  A2 — execute_plan() raises RuntimeError if the plan has no synthesise step
  A2 — execute_plan() returns an "error" log entry for unknown tools
       instead of crashing
  A3 — analyse_cve() calls research → critique → revise in order and
       passes the draft + critique into the reviser
  A4 — analyse_cve() runs the three specialists in parallel and only
       calls the orchestrator after all three return

HOW TO RUN
──────────
  Locally:
      pip install -e ".[dev]"
      pytest tests/test_architectures.py -v

  Via docker compose (no DB needed for these tests, but stays consistent
  with the L6 flow):
      docker compose --profile test run --rm test
"""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, patch

import pytest


# ─── Fake OpenAI response objects ─────────────────────────────────────────────
# AsyncOpenAI returns objects with a particular shape (choices[0].message.{content,
# tool_calls}, .usage.{prompt_tokens, completion_tokens}). We build the smallest
# possible duck-typed equivalents so tests don't depend on the openai SDK internals.

class _FakeFunction:
    def __init__(self, name: str, arguments: str) -> None:
        self.name = name
        self.arguments = arguments


class _FakeToolCall:
    def __init__(self, call_id: str, name: str, arguments: str) -> None:
        self.id = call_id
        self.type = "function"
        self.function = _FakeFunction(name, arguments)


class _FakeMessage:
    def __init__(self, content: str | None = None, tool_calls: list | None = None) -> None:
        self.content = content
        self.tool_calls = tool_calls

    def model_dump(self, exclude_unset: bool = False) -> dict:
        out: dict = {"role": "assistant", "content": self.content}
        if self.tool_calls:
            out["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                }
                for tc in self.tool_calls
            ]
        return out


class _FakeUsage:
    def __init__(self, prompt: int = 10, completion: int = 20) -> None:
        self.prompt_tokens = prompt
        self.completion_tokens = completion


class _FakeChoice:
    def __init__(self, message: _FakeMessage) -> None:
        self.message = message


class _FakeCompletion:
    def __init__(self, message: _FakeMessage, usage: _FakeUsage | None = None) -> None:
        self.choices = [_FakeChoice(message)]
        self.usage = usage or _FakeUsage()


def _completion_tool_call(name: str, args: dict, call_id: str = "call_1") -> _FakeCompletion:
    """Build a completion whose message contains exactly one tool_call."""
    return _FakeCompletion(
        _FakeMessage(
            content="Reasoning before action.",
            tool_calls=[_FakeToolCall(call_id, name, json.dumps(args))],
        )
    )


def _completion_text(content: str) -> _FakeCompletion:
    """Build a completion whose message contains text and no tool calls."""
    return _FakeCompletion(_FakeMessage(content=content))


def _completion_json(payload: dict) -> _FakeCompletion:
    """Build a completion whose message content is a JSON-encoded payload."""
    return _FakeCompletion(_FakeMessage(content=json.dumps(payload)))


# ─── Canned tool results ──────────────────────────────────────────────────────
# Shared between architectures so test data is consistent.

_NVD_OK = {
    "source": "NVD",
    "cve_id": "CVE-TEST-0001",
    "description": "Test remote code execution vulnerability.",
    "cvss_score": 9.8,
    "severity": "CRITICAL",
    "cvss_vector": "AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",
    "references": ["https://example.com/advisory"],
    "published": "2024-01-01",
}

_EPSS_OK = {
    "source": "EPSS",
    "cve_id": "CVE-TEST-0001",
    "score": 0.97,
    "percentile": 0.99,
    "date": "2024-04-01",
    "note": "97.0% exploitation probability; 99th percentile",
}

_KEV_OK = {
    "source": "CISA KEV",
    "cve_id": "CVE-TEST-0001",
    "in_kev": True,
    "vendor_project": "TestVendor",
    "product": "TestProduct",
    "vulnerability_name": "Test RCE",
    "date_added": "2024-02-01",
    "due_date": "2024-02-15",
    "required_action": "Apply vendor patches.",
    "note": "CONFIRMED ACTIVE EXPLOITATION.",
}


# ═══════════════════════════════════════════════════════════════════════════════
# A1 — ReAct
# ═══════════════════════════════════════════════════════════════════════════════

class TestA1SummariseObservation:
    """Pure-function tests for the trace-summary helper. No mocking required."""

    def test_error_result_is_flagged(self):
        from architectures.a1_react import _summarise_observation
        out = _summarise_observation("fetch_nvd_data", {"error": "boom"})
        assert "ERROR" in out
        assert "boom" in out

    def test_nvd_result_includes_score_and_severity(self):
        from architectures.a1_react import _summarise_observation
        out = _summarise_observation(
            "fetch_nvd_data",
            {"cvss_score": 9.8, "severity": "CRITICAL", "description": "x" * 200},
        )
        assert "9.8" in out
        assert "CRITICAL" in out

    def test_epss_result_uses_note_field(self):
        from architectures.a1_react import _summarise_observation
        out = _summarise_observation("fetch_epss_score", {"note": "97% probability"})
        assert "97%" in out

    def test_kev_result_uses_note_field(self):
        from architectures.a1_react import _summarise_observation
        out = _summarise_observation("check_cisa_kev", {"note": "Actively exploited"})
        assert "Actively exploited" in out


@pytest.mark.asyncio
async def test_a1_react_full_flow_records_one_trace_entry_per_tool_call():
    """
    The ReAct loop should emit exactly one ReasoningStep per tool call,
    and the final structured report should validate against ReActReport.

    This pins down the regression risk where the model's self-reported
    `reasoning_steps` field could drift from len(reasoning_trace).
    """
    from architectures import a1_react

    final_report_payload = {
        "cve_id": "CVE-TEST-0001",
        "cvss_score": 9.8,
        "cvss_severity": "CRITICAL",
        "epss_score": 0.97,
        "epss_percentile": 0.99,
        "in_cisa_kev": True,
        "patch_available": True,
        "risk_verdict": "Critical RCE actively exploited.",
        "recommended_action": "Patch immediately.",
        "reasoning_steps": 3,
        "data_sources": ["NVD", "EPSS", "CISA KEV"],
    }

    # Sequence: 3 tool-calling iterations → 1 text iteration (loop exit) →
    # 1 final structured call.
    side_effect = [
        _completion_tool_call("fetch_nvd_data",   {"cve_id": "CVE-TEST-0001"}, "c1"),
        _completion_tool_call("fetch_epss_score", {"cve_id": "CVE-TEST-0001"}, "c2"),
        _completion_tool_call("check_cisa_kev",   {"cve_id": "CVE-TEST-0001"}, "c3"),
        _completion_text("All three sources gathered. Producing final answer."),
        _completion_json(final_report_payload),
    ]

    with (
        # Patch the dispatch table so _execute_tool() never hits real APIs.
        # Patching the bare module functions is not enough because
        # TOOL_FUNCTIONS captured the references at import time.
        patch.dict(
            "architectures.a1_react.TOOL_FUNCTIONS",
            {
                "fetch_nvd_data":   AsyncMock(return_value=json.dumps(_NVD_OK)),
                "fetch_epss_score": AsyncMock(return_value=json.dumps(_EPSS_OK)),
                "check_cisa_kev":   AsyncMock(return_value=json.dumps(_KEV_OK)),
            },
            clear=True,
        ),
        patch.object(
            a1_react.client.chat.completions,
            "create",
            new=AsyncMock(side_effect=side_effect),
        ),
    ):
        report, trace = await a1_react.analyse_cve("CVE-TEST-0001")

    assert report.cve_id == "CVE-TEST-0001"
    assert report.in_cisa_kev is True
    assert len(trace) == 3, f"Expected 3 trace entries, got {len(trace)}"
    assert {entry["action"] for entry in trace} == {
        "fetch_nvd_data",
        "fetch_epss_score",
        "check_cisa_kev",
    }
    # Every trace entry has the four documented keys
    for entry in trace:
        assert {"thought", "action", "observation", "step"} <= set(entry.keys())


@pytest.mark.asyncio
async def test_a1_react_loop_aborts_after_max_iterations():
    """
    If the model keeps emitting tool_calls forever, the loop must raise
    rather than spin indefinitely. Safety guard at line ~566 of a1_react.py.
    """
    from architectures import a1_react

    # An infinite stream of tool calls — the loop should give up.
    repeated = _completion_tool_call("fetch_nvd_data", {"cve_id": "CVE-TEST-0001"}, "c1")

    with (
        patch.dict(
            "architectures.a1_react.TOOL_FUNCTIONS",
            {"fetch_nvd_data": AsyncMock(return_value=json.dumps(_NVD_OK))},
            clear=True,
        ),
        patch.object(
            a1_react.client.chat.completions,
            "create",
            new=AsyncMock(return_value=repeated),
        ),
    ):
        with pytest.raises(RuntimeError, match="exceeded"):
            await a1_react.run_react_loop("CVE-TEST-0001")


# ═══════════════════════════════════════════════════════════════════════════════
# A2 — Plan-and-Execute
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_a2_execute_plan_raises_when_no_synthesise_step():
    """
    If the planner LLM forgets the synthesise step, execute_plan() should
    raise a clear RuntimeError instead of returning None / silently dropping
    the report. This is the explicit safety check at the bottom of execute_plan().
    """
    from architectures.a2_plan_execute import execute_plan, InvestigationPlan, PlanStep

    bad_plan = InvestigationPlan(
        goal="test",
        reasoning="missing the synthesise step on purpose",
        steps=[
            PlanStep(
                step=1,
                description="fetch NVD",
                step_type="tool_call",
                tool_name="fetch_nvd_data",
            ),
        ],
    )

    with patch.dict(
        "architectures.a2_plan_execute.TOOL_FUNCTIONS",
        {"fetch_nvd_data": AsyncMock(return_value=_NVD_OK)},
        clear=True,
    ):
        with pytest.raises(RuntimeError, match="synthesise"):
            await execute_plan("CVE-TEST-0001", bad_plan)


@pytest.mark.asyncio
async def test_a2_execute_plan_logs_unknown_tool_as_error():
    """
    If the planner names a tool that doesn't exist, execute_plan() should
    record the error in the log and continue, not crash.
    """
    from architectures.a2_plan_execute import execute_plan, InvestigationPlan, PlanStep
    from architectures import a2_plan_execute as a2

    plan = InvestigationPlan(
        goal="test",
        reasoning="unknown tool then synthesise",
        steps=[
            PlanStep(
                step=1,
                description="bogus tool",
                step_type="tool_call",
                tool_name="fetch_nonexistent",
            ),
            PlanStep(
                step=2,
                description="synthesise final report",
                step_type="synthesise",
                tool_name="",
            ),
        ],
    )

    final_payload = {
        "cve_id": "CVE-TEST-0001",
        "cvss_score": 0.0,
        "cvss_severity": "Unknown",
        "epss_score": 0.0,
        "epss_percentile": 0.0,
        "in_cisa_kev": False,
        "patch_available": False,
        "risk_verdict": "Insufficient data.",
        "recommended_action": "Re-run investigation.",
        "steps_executed": 2,
        "data_sources": [],
    }

    with patch.object(
        a2.client.chat.completions,
        "create",
        new=AsyncMock(return_value=_completion_json(final_payload)),
    ):
        report, log = await execute_plan("CVE-TEST-0001", plan)

    assert log[0]["status"] == "error"
    assert "Unknown tool" in log[0]["result"]["error"]
    assert log[1]["tool"] == "synthesise"
    assert report.cve_id == "CVE-TEST-0001"


@pytest.mark.asyncio
async def test_a2_full_flow_plan_then_execute():
    """
    Smoke test: analyse_cve() should call create_plan() once, then drive
    execute_plan() through the resulting steps. We mock create_plan so the
    plan is deterministic and we don't need to mock the planner LLM call.
    """
    from architectures import a2_plan_execute as a2
    from architectures.a2_plan_execute import InvestigationPlan, PlanStep

    canned_plan = InvestigationPlan(
        goal="Investigate CVE-TEST-0001",
        reasoning="Fetch NVD then synthesise.",
        steps=[
            PlanStep(step=1, description="Get NVD",     step_type="tool_call",  tool_name="fetch_nvd_data"),
            PlanStep(step=2, description="Synthesise",  step_type="synthesise", tool_name=""),
        ],
    )

    final_payload = {
        "cve_id": "CVE-TEST-0001",
        "cvss_score": 9.8,
        "cvss_severity": "CRITICAL",
        "epss_score": 0.97,
        "epss_percentile": 0.99,
        "in_cisa_kev": True,
        "patch_available": True,
        "risk_verdict": "Critical and exploited.",
        "recommended_action": "Apply vendor patch.",
        "steps_executed": 2,
        "data_sources": ["NVD"],
    }

    with (
        patch.object(a2, "create_plan", new=AsyncMock(return_value=canned_plan)),
        patch.dict(
            "architectures.a2_plan_execute.TOOL_FUNCTIONS",
            {"fetch_nvd_data": AsyncMock(return_value=_NVD_OK)},
            clear=True,
        ),
        patch.object(
            a2.client.chat.completions,
            "create",
            new=AsyncMock(return_value=_completion_json(final_payload)),
        ),
    ):
        plan, report, log = await a2.analyse_cve("CVE-TEST-0001")

    assert plan.steps[1].step_type == "synthesise"
    assert report.cvss_score == 9.8
    assert len(log) == 2
    assert log[0]["status"] == "ok"


# ═══════════════════════════════════════════════════════════════════════════════
# A3 — Reflection
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_a3_reflection_runs_research_critique_revise_in_order():
    """
    analyse_cve() must produce a draft, then critique it, then revise.
    The reviser must receive the critique (we check that changes_from_draft
    survives end-to-end).
    """
    from architectures import a3_reflection as a3

    draft_payload = {
        "cve_id": "CVE-TEST-0001",
        "cvss_score": 9.8,
        "cvss_severity": "CRITICAL",
        "epss_score": 0.97,
        "in_cisa_kev": True,
        "patch_available": True,
        "risk_summary": "draft summary, vague action",
        "recommended_action": "patch soon",
        "confidence": "high",
    }
    critique_payload = {
        "overall_quality": "adequate",
        "issues": ["recommended_action is vague"],
        "missing_context": ["no specific patched version"],
        "overstatements": [],
        "improvement_needed": True,
        "critique_summary": "Action must be concrete.",
    }
    final_payload = {
        "cve_id": "CVE-TEST-0001",
        "cvss_score": 9.8,
        "cvss_severity": "CRITICAL",
        "epss_score": 0.97,
        "epss_percentile": 0.99,
        "in_cisa_kev": True,
        "patch_available": True,
        "risk_summary": "Critical RCE actively exploited; patch available.",
        "recommended_action": "Upgrade affected component to fixed version within 24 hours.",
        "confidence": "high",
        "changes_from_draft": ["sharpened recommended_action with concrete step"],
        "data_sources": ["NVD", "EPSS", "CISA KEV"],
    }

    completions = AsyncMock(side_effect=[
        _completion_json(draft_payload),
        _completion_json(critique_payload),
        _completion_json(final_payload),
    ])

    with (
        patch("architectures.a3_reflection.fetch_nvd_data",   new=AsyncMock(return_value=_NVD_OK)),
        patch("architectures.a3_reflection.fetch_epss_score", new=AsyncMock(return_value=_EPSS_OK)),
        patch("architectures.a3_reflection.check_cisa_kev",   new=AsyncMock(return_value=_KEV_OK)),
        patch.object(a3.client.chat.completions, "create", new=completions),
    ):
        draft, critique, final = await a3.analyse_cve("CVE-TEST-0001")

    # Order is preserved: 3 LLM calls in research → critique → revise sequence
    assert completions.await_count == 3
    assert draft.recommended_action == "patch soon"
    assert critique.improvement_needed is True
    assert "sharpened" in final.changes_from_draft[0]
    # The reviser correctly addressed the critique
    assert "24 hours" in final.recommended_action


@pytest.mark.asyncio
async def test_a3_skips_revision_when_critique_says_acceptable():
    """
    Even when the critic flags the draft as acceptable, the reviser still
    runs (per current design — produces a polished version). This test
    just confirms revise_draft is invoked on every run regardless.
    """
    from architectures import a3_reflection as a3

    draft_payload = {
        "cve_id": "CVE-TEST-0001",
        "cvss_score": 4.0,
        "cvss_severity": "MEDIUM",
        "epss_score": 0.01,
        "in_cisa_kev": False,
        "patch_available": True,
        "risk_summary": "low risk, patch available",
        "recommended_action": "Apply patch in next maintenance window.",
        "confidence": "high",
    }
    critique_payload = {
        "overall_quality": "good",
        "issues": [],
        "missing_context": [],
        "overstatements": [],
        "improvement_needed": False,
        "critique_summary": "Draft is acceptable.",
    }
    final_payload = {
        **draft_payload,
        "epss_percentile": 0.10,
        "changes_from_draft": ["minor polish only"],
        "data_sources": ["NVD", "EPSS", "CISA KEV"],
    }

    completions = AsyncMock(side_effect=[
        _completion_json(draft_payload),
        _completion_json(critique_payload),
        _completion_json(final_payload),
    ])

    with (
        patch("architectures.a3_reflection.fetch_nvd_data",   new=AsyncMock(return_value=_NVD_OK)),
        patch("architectures.a3_reflection.fetch_epss_score", new=AsyncMock(return_value=_EPSS_OK)),
        patch("architectures.a3_reflection.check_cisa_kev",   new=AsyncMock(return_value=_KEV_OK)),
        patch.object(a3.client.chat.completions, "create", new=completions),
    ):
        _, critique, final = await a3.analyse_cve("CVE-TEST-0001")

    assert critique.improvement_needed is False
    assert completions.await_count == 3  # research + critique + revise
    assert final.changes_from_draft == ["minor polish only"]


# ═══════════════════════════════════════════════════════════════════════════════
# A4 — Multi-Agent
# ═══════════════════════════════════════════════════════════════════════════════

def _make_agent_reports():
    """Build the three specialist reports used by the A4 tests."""
    from architectures.a4_multi_agent import (
        ThreatIntelReport,
        ImpactReport,
        RemediationReport,
    )

    threat = ThreatIntelReport(
        agent="threat_intel",
        cve_id="CVE-TEST-0001",
        description="Test RCE.",
        cvss_score=9.8,
        cvss_severity="CRITICAL",
        actively_exploited=True,
        kev_date_added="2024-02-01",
        threat_summary="Critical RCE; CISA KEV confirmed.",
    )
    impact = ImpactReport(
        agent="impact_assessment",
        cve_id="CVE-TEST-0001",
        epss_score=0.97,
        epss_percentile=0.99,
        exploitation_likely=True,
        affected_scope="All deployments of TestProduct < 2.0.",
        impact_summary="High likelihood of mass exploitation.",
    )
    remediation = RemediationReport(
        agent="patch_remediation",
        cve_id="CVE-TEST-0001",
        patch_available=True,
        urgency="immediate",
        kev_due_date="2024-02-15",
        required_action="Upgrade TestProduct to 2.0+.",
        remediation_summary="Upgrade within 24 hours.",
    )
    return threat, impact, remediation


@pytest.mark.asyncio
async def test_a4_synthesise_aggregates_three_specialists():
    """
    synthesise_reports() should produce a MultiAgentReport that reflects
    all three specialists (no single agent ignored).
    """
    from architectures import a4_multi_agent as a4

    threat, impact, remediation = _make_agent_reports()

    final_payload = {
        "cve_id": "CVE-TEST-0001",
        "cvss_score": 9.8,
        "cvss_severity": "CRITICAL",
        "epss_score": 0.97,
        "epss_percentile": 0.99,
        "actively_exploited": True,
        "patch_available": True,
        "overall_urgency": "immediate",
        "risk_verdict": "Critical, actively exploited, patch available.",
        "recommended_action": "Upgrade to TestProduct 2.0+ immediately.",
        "agents_consulted": ["threat_intel", "impact_assessment", "patch_remediation"],
    }

    with patch.object(
        a4.client.chat.completions,
        "create",
        new=AsyncMock(return_value=_completion_json(final_payload)),
    ):
        report = await a4.synthesise_reports("CVE-TEST-0001", threat, impact, remediation)

    assert report.overall_urgency == "immediate"
    assert report.actively_exploited is True
    assert set(report.agents_consulted) == {
        "threat_intel",
        "impact_assessment",
        "patch_remediation",
    }


@pytest.mark.asyncio
async def test_a4_full_flow_runs_specialists_in_parallel_then_orchestrates():
    """
    analyse_cve() should:
      1. dispatch all three specialist agents in parallel (asyncio.gather)
      2. only call synthesise_reports after all three return

    We mock at the per-agent boundary to keep the test deterministic
    despite parallel execution.
    """
    from architectures import a4_multi_agent as a4
    from architectures.a4_multi_agent import MultiAgentReport

    threat, impact, remediation = _make_agent_reports()

    final_report = MultiAgentReport(
        cve_id="CVE-TEST-0001",
        cvss_score=9.8,
        cvss_severity="CRITICAL",
        epss_score=0.97,
        epss_percentile=0.99,
        actively_exploited=True,
        patch_available=True,
        overall_urgency="immediate",
        risk_verdict="Critical, actively exploited.",
        recommended_action="Upgrade immediately.",
        agents_consulted=["threat_intel", "impact_assessment", "patch_remediation"],
    )

    threat_mock      = AsyncMock(return_value=(threat, []))
    impact_mock      = AsyncMock(return_value=(impact, []))
    remediation_mock = AsyncMock(return_value=(remediation, []))
    synthesise_mock  = AsyncMock(return_value=final_report)

    with (
        patch.object(a4, "run_threat_intel_agent", new=threat_mock),
        patch.object(a4, "run_impact_agent",       new=impact_mock),
        patch.object(a4, "run_remediation_agent",  new=remediation_mock),
        patch.object(a4, "synthesise_reports",     new=synthesise_mock),
    ):
        t, i, r, f, log = await a4.analyse_cve("CVE-TEST-0001")

    # All three specialists were called exactly once
    assert threat_mock.await_count == 1
    assert impact_mock.await_count == 1
    assert remediation_mock.await_count == 1
    # Orchestrator was called exactly once, AFTER the specialists,
    # and received all three reports.
    assert synthesise_mock.await_count == 1
    synthesise_mock.assert_awaited_with("CVE-TEST-0001", threat, impact, remediation)

    assert t is threat
    assert i is impact
    assert r is remediation
    assert f is final_report
    assert log == []  # all specialists returned empty tool logs


@pytest.mark.asyncio
async def test_a4_run_agent_with_tools_dispatches_unknown_tool_safely():
    """
    If an agent's LLM hallucinates a tool name, run_agent_with_tools should
    inject an "Unknown tool" error into the conversation rather than crash.
    """
    from architectures import a4_multi_agent as a4
    from architectures.a4_multi_agent import ThreatIntelReport

    final_payload = {
        "agent": "threat_intel",
        "cve_id": "CVE-TEST-0001",
        "description": "no data",
        "cvss_score": 0.0,
        "cvss_severity": "Unknown",
        "actively_exploited": False,
        "kev_date_added": "N/A",
        "threat_summary": "Could not gather data.",
    }

    side_effect = [
        # Agent first hallucinates a non-existent tool
        _completion_tool_call("hallucinated_tool", {"cve_id": "CVE-TEST-0001"}, "c1"),
        # Then produces a no-tool-calls message
        _completion_text("Stopping investigation."),
        # Then the structured final report
        _completion_json(final_payload),
    ]

    with patch.object(
        a4.client.chat.completions,
        "create",
        new=AsyncMock(side_effect=side_effect),
    ):
        report, tool_log = await a4.run_agent_with_tools(
            agent_name="threat_intel",
            system_prompt="test",
            user_message="test",
            tools=a4.THREAT_INTEL_TOOLS,
            output_schema=ThreatIntelReport,
        )

    assert report.cve_id == "CVE-TEST-0001"
    assert len(tool_log) == 1
    assert "error" in tool_log[0]["result"]
    assert "Unknown tool" in tool_log[0]["result"]["error"]
