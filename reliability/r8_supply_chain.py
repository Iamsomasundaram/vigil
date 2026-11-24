"""
VIGIL Reliability R8 (F19) — AI Supply Chain and Dependency Security
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from rich.console import Console

console = Console()

_DEFAULT_MANIFEST = "data/manifests/ai_artifacts.json"


def _checksum(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def load_manifest(path: str = _DEFAULT_MANIFEST) -> dict[str, Any]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Artifact manifest not found: {path}")
    payload = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or "artifacts" not in payload:
        raise ValueError("Manifest must be an object with an 'artifacts' list")
    return payload


def verify_artifacts(path: str = _DEFAULT_MANIFEST) -> dict[str, Any]:
    """Verify each tracked artifact's checksum against its recorded value."""
    manifest = load_manifest(path)
    results: list[dict[str, Any]] = []
    violations = 0

    for art in manifest.get("artifacts", []):
        name = art.get("name", "unknown")
        recorded = art.get("checksum", "")
        content = json.dumps(art.get("content", ""), sort_keys=True)
        actual = _checksum(content)
        ok = actual == recorded
        if not ok:
            violations += 1
        results.append(
            {
                "name": name,
                "type": art.get("type", "unknown"),
                "env": art.get("env", "unknown"),
                "provenance": art.get("provenance", "unknown"),
                "recorded_checksum": recorded[:16],
                "actual_checksum": actual[:16],
                "verified": ok,
            }
        )

    return {
        "manifest_path": path,
        "n_artifacts": len(results),
        "violations": violations,
        "integrity_ok": violations == 0,
        "artifacts": results,
    }


def can_promote(*, path: str = _DEFAULT_MANIFEST, eval_passed: bool) -> dict[str, Any]:
    """Promotion requires both integrity verification and passing evals."""
    integrity = verify_artifacts(path)
    allowed = integrity["integrity_ok"] and bool(eval_passed)
    reasons: list[str] = []
    if not integrity["integrity_ok"]:
        reasons.append("integrity_violation")
    if not eval_passed:
        reasons.append("eval_gate_failed")
    return {
        "allowed": allowed,
        "integrity_ok": integrity["integrity_ok"],
        "eval_passed": bool(eval_passed),
        "reasons": reasons or ["ok"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="F19 supply-chain demo")
    parser.add_argument("--path", default=_DEFAULT_MANIFEST)
    args = parser.parse_args()

    console.print(json.dumps(verify_artifacts(args.path), indent=2))


if __name__ == "__main__":
    main()
