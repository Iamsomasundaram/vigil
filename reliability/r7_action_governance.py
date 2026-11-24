"""
VIGIL Reliability R7 (F18) — Agent Permissions, Sandboxing, and Action Governance
"""

from __future__ import annotations

import argparse
import json
from typing import Any

from rich.console import Console

console = Console()

# Capability matrix: which roles may use which tools, and the max sandbox mode.
# Sandbox modes escalate: read_only < simulate < execute.
_SANDBOX_ORDER = {"read_only": 0, "simulate": 1, "execute": 2}

_ROLE_POLICIES: dict[str, dict[str, Any]] = {
    "viewer": {
        "allowed_tools": ["fetch_nvd_data", "fetch_epss_score"],
        "max_sandbox": "read_only",
        "sensitive_tools": [],
    },
    "analyst": {
        "allowed_tools": ["fetch_nvd_data", "fetch_epss_score", "open_ticket"],
        "max_sandbox": "simulate",
        "sensitive_tools": ["open_ticket"],
    },
    "responder": {
        "allowed_tools": ["fetch_nvd_data", "fetch_epss_score", "open_ticket", "apply_patch"],
        "max_sandbox": "execute",
        "sensitive_tools": ["open_ticket", "apply_patch"],
    },
}


def get_role_policy(role: str) -> dict[str, Any]:
    return _ROLE_POLICIES.get(role, {"allowed_tools": [], "max_sandbox": "read_only", "sensitive_tools": []})


def check_action(
    *,
    role: str,
    tool: str,
    requested_sandbox: str = "read_only",
    approved: bool = False,
) -> dict[str, Any]:
    """Evaluate whether an action is permitted under least-privilege policy."""
    policy = get_role_policy(role)
    reasons: list[str] = []

    if requested_sandbox not in _SANDBOX_ORDER:
        return {
            "role": role,
            "tool": tool,
            "requested_sandbox": requested_sandbox,
            "allowed": False,
            "effective_sandbox": "read_only",
            "requires_approval": False,
            "reasons": ["invalid_sandbox_mode"],
        }

    tool_allowed = tool in policy["allowed_tools"]
    if not tool_allowed:
        reasons.append("tool_not_in_role_scope")

    within_sandbox = _SANDBOX_ORDER[requested_sandbox] <= _SANDBOX_ORDER[policy["max_sandbox"]]
    if not within_sandbox:
        reasons.append("sandbox_exceeds_role_limit")

    is_sensitive = tool in policy["sensitive_tools"]
    requires_approval = is_sensitive and requested_sandbox == "execute"
    approval_ok = (not requires_approval) or approved
    if requires_approval and not approved:
        reasons.append("requires_human_approval")

    allowed = tool_allowed and within_sandbox and approval_ok
    effective = requested_sandbox if allowed else "read_only"

    return {
        "role": role,
        "tool": tool,
        "requested_sandbox": requested_sandbox,
        "allowed": allowed,
        "effective_sandbox": effective,
        "requires_approval": requires_approval,
        "reasons": reasons or ["ok"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="F18 action governance demo")
    parser.add_argument("--role", default="analyst")
    parser.add_argument("--tool", default="apply_patch")
    parser.add_argument("--sandbox", default="execute")
    parser.add_argument("--approved", action="store_true", default=False)
    args = parser.parse_args()

    result = check_action(
        role=args.role,
        tool=args.tool,
        requested_sandbox=args.sandbox,
        approved=args.approved,
    )
    console.print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
