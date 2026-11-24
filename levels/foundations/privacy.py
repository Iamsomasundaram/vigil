"""
VIGIL Foundations F15 — Privacy and Safe Logging
"""

from __future__ import annotations

import argparse
import json
import re
from typing import Any

from rich.console import Console

console = Console()

_PATTERNS: list[tuple[str, re.Pattern[str], str]] = [
    ("email", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"), "<REDACTED_EMAIL>"),
    ("ipv4", re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"), "<REDACTED_IP>"),
    ("api_key", re.compile(r"\b(?:sk|pk)-[A-Za-z0-9_-]{16,}\b"), "<REDACTED_KEY>"),
    ("token", re.compile(r"\b(?:token|secret|password)\s*[:=]\s*[^\s,;]+", re.IGNORECASE), "<REDACTED_SECRET_FIELD>"),
]


def redact_text(text: str) -> dict[str, Any]:
    """Redact common sensitive patterns and return findings metadata."""
    out = text
    findings: list[dict[str, Any]] = []

    for kind, pattern, replacement in _PATTERNS:
        matches = list(pattern.finditer(out))
        if not matches:
            continue
        findings.append({"type": kind, "count": len(matches)})
        out = pattern.sub(replacement, out)

    return {
        "redacted_text": out,
        "findings": findings,
        "changed": out != text,
    }


def safe_log_snapshot(payload: Any) -> Any:
    """Recursively redact strings inside nested log payload objects."""
    if isinstance(payload, str):
        return redact_text(payload)["redacted_text"]
    if isinstance(payload, list):
        return [safe_log_snapshot(x) for x in payload]
    if isinstance(payload, dict):
        return {str(k): safe_log_snapshot(v) for k, v in payload.items()}
    return payload


def privacy_report(text: str, sample_payload: dict[str, Any] | None = None) -> dict[str, Any]:
    red = redact_text(text)
    payload = sample_payload or {"message": text, "source": "ui"}
    return {
        "input_length": len(text),
        "changed": red["changed"],
        "findings": red["findings"],
        "redacted_text": red["redacted_text"],
        "safe_log_snapshot": safe_log_snapshot(payload),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="F15 privacy redaction demo")
    parser.add_argument(
        "text",
        nargs="?",
        default="Contact ops@example.com from 10.20.30.40 with token=abc123 and key sk-demo-1234567890123456",
    )
    args = parser.parse_args()

    rep = privacy_report(args.text)
    console.print(json.dumps(rep, indent=2))


if __name__ == "__main__":
    main()
