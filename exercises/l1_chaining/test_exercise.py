"""Grader for exercise L1 (imports the learner's start.py)."""

from __future__ import annotations

from start import run_chain


def test_empty_steps_returns_initial():
    assert run_chain([], "seed") == "seed"


def test_threads_output_into_next_step():
    steps = [lambda x: x + 1, lambda x: x * 2, lambda x: x - 3]
    # ((5 + 1) * 2) - 3 = 9
    assert run_chain(steps, 5) == 9


def test_works_with_strings():
    steps = [str.strip, str.upper, lambda s: s + "!"]
    assert run_chain(steps, "  log4j  ") == "LOG4J!"
