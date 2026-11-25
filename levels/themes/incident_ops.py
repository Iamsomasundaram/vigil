"""
VIGIL Theme T1 — Incident Response Ops
"""

from __future__ import annotations

import argparse
import json
import re

from rich.console import Console
from rich.table import Table

from vigil.models import IncidentOpsReport

console = Console()

_CRITICAL_TERMS = {
    "data breach",
    "exfiltration",
    "remote code execution",
    "rce",
    "production down",
    "all regions down",
    "payment failures",
}

_HIGH_TERMS = {
    "latency",
    "error rate",
    "degraded",
    "timeout",
    "auth failure",
    "queue backlog",
    "service unavailable",
}

_DOMAIN_RULES: list[tuple[str, str]] = [
    ("auth", "identity"),
    ("login", "identity"),
    ("payment", "payments"),
    ("checkout", "payments"),
    ("database", "data"),
    ("postgres", "data"),
    ("latency", "performance"),
    ("timeout", "performance"),
    ("api gateway", "network"),
    ("dns", "network"),
]


def _contains_any(text: str, terms: set[str]) -> bool:
    # Whole-word match, so "rce" does not fire inside "resource".
    lowered = text.lower()
    return any(re.search(rf"\b{re.escape(term)}\b", lowered) for term in terms)


def _likely_domains(text: str, signals: list[str]) -> list[str]:
    corpus = f"{text} {' '.join(signals)}".lower()
    domains: list[str] = []
    for needle, domain in _DOMAIN_RULES:
        if needle in corpus and domain not in domains:
            domains.append(domain)
    return domains or ["application"]


def analyse_incident(
    *,
    alert_text: str,
    service_name: str,
    customer_impact: bool,
    signals: list[str] | None = None,
) -> IncidentOpsReport:
    """Classify incident urgency and return a structured response plan."""
    sigs = [s.strip() for s in (signals or []) if s.strip()]
    corpus = f"{alert_text} {' '.join(sigs)}"

    is_critical = customer_impact and _contains_any(corpus, _CRITICAL_TERMS)
    is_high = _contains_any(corpus, _HIGH_TERMS)

    if is_critical:
        severity = "Critical"
        track = "containment"
        urgency = 15
        actions = [
            "Declare incident and assign an incident commander immediately.",
            "Apply containment: isolate impacted entry points or disable risky feature flags.",
            "Open an executive update channel and publish a 15-minute status cadence.",
        ]
        targets = ["on-call-sre", "security-incident-manager", "engineering-director"]
        reasoning = "Customer impact plus critical exploit/outage language indicates immediate containment."
    elif is_high or customer_impact:
        severity = "High"
        track = "mitigation"
        urgency = 60
        actions = [
            "Stabilize service with rollback, scaling, or traffic controls.",
            "Create a mitigation task list with owners and time-boxed checkpoints.",
            "Communicate customer impact scope and expected recovery window.",
        ]
        targets = ["on-call-sre", "service-owner"]
        reasoning = "Signals indicate production degradation needing urgent mitigation."
    else:
        severity = "Medium"
        track = "monitor"
        urgency = 240
        actions = [
            "Monitor key SLO indicators and alert thresholds for the next 24 hours.",
            "Prepare rollback and mitigation playbooks if thresholds worsen.",
            "Schedule follow-up review and root-cause analysis tasking.",
        ]
        targets = ["service-owner"]
        reasoning = "No direct customer impact and no severe keywords; monitor with readiness to escalate."

    summary = (
        f"{service_name} incident classified as {severity}. "
        f"Route to {track} track with response target within {urgency} minutes."
    )

    return IncidentOpsReport(
        service_name=service_name,
        severity=severity,
        track=track,
        summary=summary,
        urgency_minutes=urgency,
        likely_domains=_likely_domains(alert_text, sigs),
        immediate_actions=actions,
        escalation_targets=targets,
        reasoning=reasoning,
    )


def render_report(report: IncidentOpsReport) -> None:
    table = Table(title="T1 Incident Response Report")
    table.add_column("Field")
    table.add_column("Value")
    table.add_row("Service", report.service_name)
    table.add_row("Severity", report.severity)
    table.add_row("Track", report.track)
    table.add_row("Urgency", f"{report.urgency_minutes} minutes")
    table.add_row("Domains", ", ".join(report.likely_domains))
    console.print(table)
    console.print("Summary:", report.summary)
    console.print("Actions:")
    for i, action in enumerate(report.immediate_actions, 1):
        console.print(f"{i}. {action}")


def main() -> None:
    parser = argparse.ArgumentParser(description="T1 incident response ops theme")
    parser.add_argument("alert_text", nargs="?", default="Payment API error rate surged and customer checkouts are failing")
    parser.add_argument("--service", default="payments-api")
    parser.add_argument("--customer-impact", action="store_true", default=False)
    parser.add_argument("--signal", action="append", default=[])
    args = parser.parse_args()

    report = analyse_incident(
        alert_text=args.alert_text,
        service_name=args.service,
        customer_impact=args.customer_impact,
        signals=args.signal,
    )
    render_report(report)
    console.print(json.dumps(report.model_dump(), indent=2))


if __name__ == "__main__":
    main()
