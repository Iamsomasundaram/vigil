"""Repo-side grader for the learner exercises in `exercises/`.

This proves two things for every exercise:
  1. The reference `solution.py` actually satisfies the task.
  2. The shipped `start.py` is still an unfinished stub (raises NotImplementedError),
     so the in-folder grader is meaningful (fails before the learner fills it in).

The default test suite uses `testpaths = ["tests"]`, so the in-folder
`exercises/**/test_exercise.py` graders are NOT collected here — only the learner
runs those against their own `start.py`.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

EXERCISES = Path(__file__).resolve().parent.parent / "exercises"


def _load(path: Path, unique_name: str):
    spec = importlib.util.spec_from_file_location(unique_name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


# ─── L0: prompt construction ──────────────────────────────────────────────────

def test_l0_solution_builds_valid_messages():
    sol = _load(EXERCISES / "l0_prompting" / "solution.py", "ex_l0_solution")
    msgs = sol.build_analysis_messages("CVE-2021-44228", "You are an analyst.")
    assert len(msgs) == 2
    assert msgs[0] == {"role": "system", "content": "You are an analyst."}
    assert msgs[1]["role"] == "user"
    assert "CVE-2021-44228" in msgs[1]["content"]


def test_l0_start_is_unfinished_stub():
    start = _load(EXERCISES / "l0_prompting" / "start.py", "ex_l0_start")
    with pytest.raises(NotImplementedError):
        start.build_analysis_messages("CVE-2021-44228", "role")


# ─── L1: prompt chaining ──────────────────────────────────────────────────────

def test_l1_solution_threads_steps():
    sol = _load(EXERCISES / "l1_chaining" / "solution.py", "ex_l1_solution")
    assert sol.run_chain([], "seed") == "seed"
    assert sol.run_chain([lambda x: x + 1, lambda x: x * 2, lambda x: x - 3], 5) == 9


def test_l1_start_is_unfinished_stub():
    start = _load(EXERCISES / "l1_chaining" / "start.py", "ex_l1_start")
    with pytest.raises(NotImplementedError):
        start.run_chain([], "seed")


# ─── L4: tool dispatch ────────────────────────────────────────────────────────

def test_l4_solution_routes_and_degrades():
    sol = _load(EXERCISES / "l4_tool_dispatch" / "solution.py", "ex_l4_solution")
    registry = {"fetch_nvd_data": lambda cve_id: {"cve_id": cve_id, "cvss_score": 10.0}}
    assert sol.dispatch_tool("fetch_nvd_data", {"cve_id": "CVE-X"}, registry)["cvss_score"] == 10.0
    assert sol.dispatch_tool("nope", {}, registry) == {"error": "Unknown tool: nope"}


def test_l4_start_is_unfinished_stub():
    start = _load(EXERCISES / "l4_tool_dispatch" / "start.py", "ex_l4_start")
    with pytest.raises(NotImplementedError):
        start.dispatch_tool("x", {}, {})
