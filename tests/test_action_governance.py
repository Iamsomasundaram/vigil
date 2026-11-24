from __future__ import annotations

from reliability.r7_action_governance import check_action


def test_viewer_cannot_execute_sensitive_tool():
    out = check_action(role="viewer", tool="apply_patch", requested_sandbox="execute")
    assert out["allowed"] is False
    assert "tool_not_in_role_scope" in out["reasons"]


def test_responder_requires_approval_for_execute_patch():
    without = check_action(role="responder", tool="apply_patch", requested_sandbox="execute", approved=False)
    assert without["allowed"] is False
    assert without["requires_approval"] is True

    with_approval = check_action(role="responder", tool="apply_patch", requested_sandbox="execute", approved=True)
    assert with_approval["allowed"] is True
    assert with_approval["effective_sandbox"] == "execute"


def test_sandbox_exceeds_role_limit_is_denied():
    out = check_action(role="analyst", tool="open_ticket", requested_sandbox="execute", approved=True)
    assert out["allowed"] is False
    assert "sandbox_exceeds_role_limit" in out["reasons"]
