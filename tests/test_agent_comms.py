from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["handoff", "debate", "blackboard"])
async def test_a4_collaborate_modes_return_consensus(mode: str):
    from architectures.a4_multi_agent import (
        ImpactReport,
        MultiAgentReport,
        RemediationReport,
        ThreatIntelReport,
        collaborate,
    )

    threat = ThreatIntelReport(
        agent="threat_intel",
        cve_id="CVE-TEST-2",
        description="desc",
        cvss_score=9.1,
        cvss_severity="CRITICAL",
        actively_exploited=True,
        kev_date_added="2024-01-01",
        threat_summary="active exploitation observed",
    )
    impact = ImpactReport(
        agent="impact_assessment",
        cve_id="CVE-TEST-2",
        epss_score=0.82,
        epss_percentile=0.95,
        exploitation_likely=True,
        affected_scope="internet exposed",
        impact_summary="high impact",
    )
    remediation = RemediationReport(
        agent="patch_remediation",
        cve_id="CVE-TEST-2",
        patch_available=True,
        urgency="immediate",
        kev_due_date="2024-01-10",
        required_action="patch now",
        remediation_summary="apply vendor fix",
    )
    final = MultiAgentReport(
        cve_id="CVE-TEST-2",
        cvss_score=9.1,
        cvss_severity="CRITICAL",
        epss_score=0.82,
        epss_percentile=0.95,
        actively_exploited=True,
        patch_available=True,
        overall_urgency="immediate",
        risk_verdict="critical and exploited",
        recommended_action="immediate patching",
        agents_consulted=["threat_intel", "impact_assessment", "patch_remediation"],
    )

    with patch(
        "architectures.a4_multi_agent.analyse_cve",
        new=AsyncMock(return_value=(threat, impact, remediation, final, [])),
    ):
        out = await collaborate("CVE-TEST-2", mode=mode, rounds=2)

    assert out.mode == mode
    assert out.final_verdict == "critical and exploited"
    assert len(out.transcript) >= 2
