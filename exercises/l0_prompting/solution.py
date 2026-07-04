"""Exercise L0 — reference solution."""

from __future__ import annotations


def build_analysis_messages(cve_id: str, system_role: str) -> list[dict]:
    return [
        {"role": "system", "content": system_role},
        {"role": "user", "content": f"Analyse {cve_id} and summarise its risk."},
    ]
