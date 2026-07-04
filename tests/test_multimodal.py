from __future__ import annotations

import base64
import json
import sys

import pytest


# ─── fake OpenAI plumbing ──────────────────────────────────────────────────

class _FakeUsage:
    prompt_tokens = 11
    completion_tokens = 7


class _FakeMessage:
    def __init__(self, content: str):
        self.content = content


class _FakeChoice:
    def __init__(self, content: str):
        self.message = _FakeMessage(content)


class _FakeResponse:
    def __init__(self, content: str):
        self.choices = [_FakeChoice(content)]
        self.usage = _FakeUsage()


_EXTRACT_JSON = json.dumps({
    "cve_id": "CVE-2021-44228",
    "affected_product": "Apache Log4j 2",
    "claimed_severity": "Critical",
    "source_type": "image",
    "extracted_fields": [{"name": "cvss", "value": "10.0"}],
    "grounding_quotes": ["Remote code execution via JNDI lookup"],
})


def _patch_create(monkeypatch, capture: list):
    """Replace the module's OpenAI create() with an async stub that records kwargs."""
    from levels import l4b_multimodal as m

    async def fake_create(**kwargs):
        capture.append(kwargs)
        return _FakeResponse(_EXTRACT_JSON)

    monkeypatch.setattr(m.client.chat.completions, "create", fake_create)
    return m


# ─── image message construction ────────────────────────────────────────────

def test_build_image_messages_url_passthrough():
    from levels.l4b_multimodal import build_image_messages

    messages = build_image_messages("https://example.com/advisory.png")
    parts = messages[-1]["content"]
    image_part = next(p for p in parts if p["type"] == "image_url")
    assert image_part["image_url"]["url"] == "https://example.com/advisory.png"


def test_build_image_messages_local_file_base64(tmp_path):
    from levels.l4b_multimodal import build_image_messages

    img = tmp_path / "advisory.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\nFAKEPNGBYTES")

    messages = build_image_messages(str(img))
    parts = messages[-1]["content"]
    image_part = next(p for p in parts if p["type"] == "image_url")
    url = image_part["image_url"]["url"]

    assert url.startswith("data:image/png;base64,")
    decoded = base64.b64decode(url.split(",", 1)[1])
    assert decoded == b"\x89PNG\r\n\x1a\nFAKEPNGBYTES"


def test_build_image_messages_missing_file_raises():
    from levels.l4b_multimodal import build_image_messages

    with pytest.raises(FileNotFoundError):
        build_image_messages("does/not/exist.png")


# ─── image extraction (model stubbed) ──────────────────────────────────────

@pytest.mark.asyncio
async def test_extract_from_image_returns_structured(monkeypatch):
    capture: list = []
    m = _patch_create(monkeypatch, capture)
    m._reset_usage()

    extract = await m.extract_from_image("https://example.com/advisory.png")

    assert extract.cve_id == "CVE-2021-44228"
    assert extract.source_type == "image"
    assert extract.extracted_fields[0].name == "cvss"
    assert extract.grounding_quotes

    # an image_url message part was actually sent to the model
    sent_parts = capture[0]["messages"][-1]["content"]
    assert any(p["type"] == "image_url" for p in sent_parts)

    usage = m.get_usage()
    assert usage["total_tokens"] == 18


# ─── pdf extraction (parser + model stubbed) ───────────────────────────────

@pytest.mark.asyncio
async def test_extract_from_pdf_grounds_on_extracted_text(monkeypatch):
    capture: list = []
    m = _patch_create(monkeypatch, capture)
    m._reset_usage()

    monkeypatch.setattr(
        m, "extract_pdf_text",
        lambda *_a, **_k: "CVE-2021-44228 affects Apache Log4j 2. Severity: Critical.",
    )

    extract = await m.extract_from_pdf("bulletin.pdf")

    assert extract.source_type == "pdf"
    assert extract.cve_id == "CVE-2021-44228"
    # the extracted text was passed to the model
    sent = capture[0]["messages"][-1]["content"]
    assert "Apache Log4j 2" in sent


def test_extract_pdf_text_missing_pypdf_degrades(monkeypatch):
    from levels.l4b_multimodal import extract_pdf_text

    # Simulate pypdf being unavailable.
    monkeypatch.setitem(sys.modules, "pypdf", None)

    with pytest.raises(RuntimeError) as exc:
        extract_pdf_text("anything.pdf")
    assert "pypdf" in str(exc.value).lower()


def test_extract_pdf_text_missing_file_raises():
    pytest.importorskip("pypdf")
    from levels.l4b_multimodal import extract_pdf_text

    with pytest.raises(FileNotFoundError):
        extract_pdf_text("no/such/file.pdf")
