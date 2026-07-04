from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_a2_hitl_requires_approval_then_executes():
    from architectures.a2_plan_execute import (
        InvestigationPlan,
        PlanStep,
        PlanExecuteReport,
        get_gated_run_details,
        start_gated_run,
        submit_human_decision,
    )
    from vigil.models import HumanDecision

    plan = InvestigationPlan(
        goal="Assess CVE-TEST-1",
        reasoning="test",
        steps=[
            PlanStep(step=1, description="critical containment validation", step_type="tool_call", tool_name="fetch_nvd_data"),
            PlanStep(step=2, description="final synthesis", step_type="synthesise", tool_name=""),
        ],
    )
    report = PlanExecuteReport(
        cve_id="CVE-TEST-1",
        cvss_score=9.8,
        cvss_severity="CRITICAL",
        epss_score=0.9,
        epss_percentile=0.95,
        in_cisa_kev=True,
        patch_available=True,
        risk_verdict="critical",
        recommended_action="patch",
        steps_executed=2,
        data_sources=["NVD"],
    )

    with (
        patch("architectures.a2_plan_execute.create_plan", new=AsyncMock(return_value=plan)),
        patch("architectures.a2_plan_execute.execute_plan", new=AsyncMock(return_value=(report, [{"step": 1}]))),
    ):
        state = await start_gated_run("CVE-TEST-1")
        assert state.state == "pending_plan_approval"

        first = await submit_human_decision(
            HumanDecision(gate_id=state.open_gate.gate_id, decision="approve", actor="analyst")
        )
        assert first.state == "pending_action_approval"

        second = await submit_human_decision(
            HumanDecision(gate_id=first.open_gate.gate_id, decision="approve", actor="analyst")
        )
        assert second.state == "done"

        details = get_gated_run_details(second.run_id)
        assert details is not None
        assert details["report"].cve_id == "CVE-TEST-1"
