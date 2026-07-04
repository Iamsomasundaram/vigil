"""Grader for exercise L0.

By default this imports the learner's `start.py`. Fill in start.py until it passes.
The repository's own test suite grades `solution.py` separately (tests/test_exercises.py).
"""

from __future__ import annotations

from start import build_analysis_messages


def test_returns_two_messages():
    msgs = build_analysis_messages("CVE-2021-44228", "You are an analyst.")
    assert isinstance(msgs, list)
    assert len(msgs) == 2


def test_system_message_carries_role():
    role = "You are a senior cybersecurity analyst."
    msgs = build_analysis_messages("CVE-2021-44228", role)
    assert msgs[0] == {"role": "system", "content": role}


def test_user_message_mentions_cve():
    msgs = build_analysis_messages("CVE-2021-44228", "analyst")
    assert msgs[1]["role"] == "user"
    assert "CVE-2021-44228" in msgs[1]["content"]
