from __future__ import annotations

import json

from reliability.r8_supply_chain import can_promote, verify_artifacts


def test_verify_artifacts_ok_for_seeded_manifest():
    rep = verify_artifacts("data/manifests/ai_artifacts.json")
    assert rep["n_artifacts"] >= 1
    assert rep["integrity_ok"] is True
    assert rep["violations"] == 0


def test_verify_artifacts_detects_tampering(tmp_path):
    manifest = tmp_path / "m.json"
    manifest.write_text(
        json.dumps(
            {
                "version": "1.0",
                "artifacts": [
                    {
                        "name": "prompt",
                        "type": "prompt",
                        "env": "prod",
                        "provenance": "test",
                        "content": "hello",
                        "checksum": "deadbeef",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    rep = verify_artifacts(str(manifest))
    assert rep["integrity_ok"] is False
    assert rep["violations"] == 1


def test_can_promote_requires_integrity_and_eval():
    ok = can_promote(path="data/manifests/ai_artifacts.json", eval_passed=True)
    assert ok["allowed"] is True

    blocked = can_promote(path="data/manifests/ai_artifacts.json", eval_passed=False)
    assert blocked["allowed"] is False
    assert "eval_gate_failed" in blocked["reasons"]
