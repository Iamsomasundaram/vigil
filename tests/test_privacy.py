from __future__ import annotations

from levels.foundations.privacy import privacy_report, redact_text, safe_log_snapshot


def test_redact_text_detects_and_replaces_sensitive_patterns():
    src = "Email ops@example.com IP 10.1.2.3 key sk-demo-1234567890123456"
    out = redact_text(src)

    assert out["changed"] is True
    assert "<REDACTED_EMAIL>" in out["redacted_text"]
    assert "<REDACTED_IP>" in out["redacted_text"]


def test_safe_log_snapshot_redacts_nested_payload():
    payload = {
        "msg": "password=supersecret",
        "nested": ["token: abc", {"email": "alice@example.com"}],
    }
    out = safe_log_snapshot(payload)
    assert "REDACTED" in out["msg"]
    assert "REDACTED" in out["nested"][1]["email"]


def test_privacy_report_shape():
    out = privacy_report("reach me at bob@example.com")
    assert "safe_log_snapshot" in out
    assert isinstance(out["findings"], list)
