# F2 — Multimodal Inputs: Vision & Document Parsing

- **Status:** Implemented
- **Axis:** Foundations (GenAI literacy) — new capability dimension
- **New module:** `levels/l4b_multimodal.py` (sits beside L4 tool use)
- **Depends on:** L1 (structured output), L4 (tool/grounding patterns)

---

## Problem / Motivation

Everything in Vigil is text-only. Real security work involves **images** (a screenshot
of a vendor advisory, an exploit-chain diagram, a dashboard) and **documents** (PDF
security bulletins, vendor patch notes). A learner never sees how a multimodal model
reads an image or how a document is parsed, extracted, and grounded. The project's own
readiness checklist marks multimodal "N/A" — F2 closes that gap.

## Teaching Goal

**A learner sends an image (advisory screenshot) and a PDF (patch bulletin) to a
vision-capable model and extracts structured CVE data from them**, learning how
multimodal prompts are constructed (image_url / base64 parts), and the difference
between OCR-style extraction and true visual reasoning.

## Goals

- **Vision input** — accept an image (URL or local file → base64) and extract a
  structured `AdvisoryExtract` (CVE id, affected product, severity claims, dates).
- **Document parsing** — accept a PDF/HTML advisory, extract text, then summarize +
  structure it; show the model grounding on the extracted text.
- **Structured output** — reuse the strict Pydantic/JSON-schema convention.
- **Graceful degradation** — if a non-vision model is configured, fail with a clear
  message; if PDF parsing lib missing, skip with guidance.

## Non-Goals

- Audio/video (a future spec); image generation (out of scope for a security tool).
- Heavy OCR pipelines — use the model's native vision + a light text extractor.

## Design

```
image (file/url) ─► base64 ─► chat.completions(messages=[{type:"image_url"...}]) ─► AdvisoryExtract
pdf  (file)      ─► extract_text() ─► chat.completions(text) ─► AdvisoryExtract
                                   └─ grounded: quotes lines it used
```

## Proposed Files

- **New** `levels/l4b_multimodal.py` — `extract_from_image()`, `extract_from_pdf()`, CLI.
- **Edit** `vigil/models.py` — `AdvisoryExtract`.
- **Edit** `vigil/api.py` — `POST /l4b/image` (multipart/url), `POST /l4b/pdf`.
- **Edit** `pyproject.toml` — new extra `multimodal = ["pypdf>=4.0"]`.
- **New** `data/samples/` — a sample advisory image + PDF for offline demo.
- **New** `tests/test_multimodal.py` — stub the model; assert message-part construction
  and structured extraction.
- **Edit** `ui/app.py` — an "L4b — Multimodal" page with image/PDF upload.

## Data Models (`vigil/models.py`)

```python
class AdvisoryExtract(_Base):
    cve_id: str | None
    affected_product: str | None
    claimed_severity: str | None
    source_type: str           # "image" | "pdf"
    extracted_fields: dict[str, str]
    grounding_quotes: list[str]
```

## API & CLI Surface

- `POST /l4b/image` (image_url or upload) → `AdvisoryExtract`.
- `POST /l4b/pdf` (upload) → `AdvisoryExtract`.
- CLI: `python levels/l4b_multimodal.py --image advisory.png`
- CLI: `python levels/l4b_multimodal.py --pdf bulletin.pdf`

## Tests (`tests/test_multimodal.py`)

- Image path builds the correct `image_url` / base64 message part (model stubbed).
- PDF path extracts text and passes it to the model (parser stubbed/sample file).
- Missing-vision-model and missing-`pypdf` cases degrade with clear errors.

## Acceptance Criteria

- [ ] An advisory screenshot yields a populated `AdvisoryExtract`.
- [ ] A PDF bulletin yields a populated `AdvisoryExtract` with grounding quotes.
- [ ] Non-vision model / missing parser degrade gracefully.
- [ ] Token tracking + conventions followed; UI page works.

## Open Questions

- Pin a vision model name via env (`OPENAI_VISION_MODEL`, default `gpt-4o-mini`)?
- Cap PDF size / pages to control cost — propose first 8 pages.
