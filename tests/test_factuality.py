from __future__ import annotations

from levels.foundations.factuality import factuality_check, split_claims


def test_split_claims_breaks_sentences():
    claims = split_claims("A is true. B is true! C is uncertain?")
    assert len(claims) == 3


def test_factuality_check_flags_unsupported_claims():
    out = factuality_check(
        answer_text="Log4j has RCE. Vendor patch is available. Exploit affects all routers.",
        evidence_snippets=[
            "Log4j vulnerability allows remote code execution.",
            "A vendor patch is available for impacted versions.",
        ],
        support_threshold=0.4,
    )

    assert out["total_claims"] == 3
    assert out["supported_claims"] >= 2
    assert out["abstain_recommended"] is True
    assert any("routers" in c.lower() for c in out["unsupported_claims"])
