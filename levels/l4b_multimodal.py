"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  VIGIL — Level 4b: Multimodal Inputs (Vision & Document Parsing)             ║
║                                                                              ║
║  The agent reads an IMAGE (advisory screenshot) or a PDF (patch bulletin)   ║
║  and extracts structured CVE data from it — grounded in what it actually    ║
║  saw or read, not training memory.                                          ║
╚══════════════════════════════════════════════════════════════════════════════╝

CONCEPTS COVERED
────────────────
  1. Multimodal prompts   — messages whose `content` is a list of typed parts
  2. image_url / base64   — how a vision model receives a picture
  3. Document parsing     — PDF → text → structured extraction
  4. Visual grounding     — quoting the exact lines/phrases the answer relied on
  5. Graceful degradation — clear errors when vision/parsing is unavailable

WHY MULTIMODAL?
───────────────
  Every other level in Vigil is text-only. Real security work is not:
    • A vendor advisory arrives as a screenshot pasted into a ticket.
    • A patch bulletin is a PDF, not an API response.
    • An exploit write-up includes a diagram.

  A modern model can READ these directly. Instead of asking a human to
  re-type an advisory, the model looks at the image and pulls out the
  CVE id, affected product, and severity claims — then tells you which
  lines it relied on so the extraction stays auditable.

HOW A VISION PROMPT IS BUILT
────────────────────────────
  A normal message:
    {"role": "user", "content": "Analyse CVE-2021-44228"}

  A multimodal message — `content` becomes a LIST of parts:
    {"role": "user", "content": [
        {"type": "text",      "text": "Extract the advisory fields."},
        {"type": "image_url", "image_url": {"url": "https://.../advisory.png"}},
    ]}

  A LOCAL image is sent as a base64 data URI:
    {"type": "image_url",
     "image_url": {"url": "data:image/png;base64,<...>"}}

  PDFs are different — vision models don't read PDFs natively here, so we
  EXTRACT the text first (pypdf), then send that text. The model grounds
  on the extracted text and quotes the lines it used.

RUN THIS FILE
─────────────
  python levels/l4b_multimodal.py --image data/samples/advisory.png
  python levels/l4b_multimodal.py --image https://example.com/advisory.png
  python levels/l4b_multimodal.py --pdf   data/samples/bulletin.pdf
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import mimetypes
import os
from pathlib import Path

from dotenv import load_dotenv
from openai import AsyncOpenAI
from pydantic import BaseModel, ConfigDict

from vigil.models import AdvisoryExtract

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

load_dotenv(Path(__file__).parent.parent / ".env")

console = Console()
client  = AsyncOpenAI(timeout=60.0)

# A vision-capable model is required for the image path. Default to gpt-4o-mini,
# which supports both vision and structured (json_schema) output.
VISION_MODEL = os.getenv("OPENAI_VISION_MODEL", os.getenv("OPENAI_MODEL", "gpt-4o-mini"))

# Cap how much of a PDF we read, to control cost on large bulletins.
PDF_PAGE_CAP = int(os.getenv("VIGIL_PDF_PAGE_CAP", "8"))


# ─── TOKEN USAGE TRACKING ─────────────────────────────────────────────────────
_usage: dict = {"prompt_tokens": 0, "completion_tokens": 0}

def _reset_usage() -> None:
    global _usage
    _usage = {"prompt_tokens": 0, "completion_tokens": 0}

def _track(response) -> None:
    if hasattr(response, "usage") and response.usage:
        _usage["prompt_tokens"]     += response.usage.prompt_tokens or 0
        _usage["completion_tokens"] += response.usage.completion_tokens or 0

def get_usage() -> dict:
    pt   = _usage["prompt_tokens"]
    ct   = _usage["completion_tokens"]
    cost = (pt * 0.150 + ct * 0.600) / 1_000_000
    return {
        "prompt_tokens":      pt,
        "completion_tokens":  ct,
        "total_tokens":       pt + ct,
        "estimated_cost_usd": round(cost, 6),
    }


# ─── SCHEMA HELPERS ───────────────────────────────────────────────────────────
# (Same strict-schema pattern as L1–L4 — see l1_chain.py for the full rationale.)

def _strict_schema(model) -> dict:
    schema = model.model_json_schema()
    _apply_required(schema)
    return schema


def _apply_required(schema: dict) -> None:
    if "properties" in schema:
        schema["required"] = list(schema["properties"].keys())
    for sub in schema.get("$defs", {}).values():
        _apply_required(sub)


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid")


SYSTEM_PROMPT = (
    "You are a security analyst extracting structured data from a vulnerability "
    "advisory. Read ONLY what is shown in the provided image or text. Do not add "
    "facts from training memory. If a field is not present, set it to null. "
    "Populate `grounding_quotes` with the exact phrases/lines you relied on so the "
    "extraction can be audited."
)

EXTRACT_INSTRUCTION = (
    "Extract the CVE identifier, affected product, claimed severity, and any other "
    "notable fields (dates, CVSS, affected versions) into the structured schema. "
    "Quote the source lines you used in `grounding_quotes`."
)


# ─── IMAGE INPUT ──────────────────────────────────────────────────────────────

def _image_url_part(image: str) -> dict:
    """Build the `image_url` message part for a URL, data URI, or local file.

    Remote URLs and data URIs are passed through untouched. A local path is read
    and encoded as a base64 data URI so the model receives the bytes directly.
    """
    if image.startswith(("http://", "https://", "data:")):
        return {"type": "image_url", "image_url": {"url": image}}

    path = Path(image)
    if not path.exists():
        raise FileNotFoundError(f"Image not found: {image}")

    mime = mimetypes.guess_type(str(path))[0] or "image/png"
    b64  = base64.b64encode(path.read_bytes()).decode("ascii")
    return {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}}


def build_image_messages(image: str) -> list[dict]:
    """Construct the multimodal message list for a vision request.

    Exposed separately so tests can assert the message-part shape without a
    network call.
    """
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": [
            {"type": "text", "text": EXTRACT_INSTRUCTION},
            _image_url_part(image),
        ]},
    ]


async def extract_from_image(image: str) -> AdvisoryExtract:
    """Send an image (URL, data URI, or local file) to a vision model and extract
    a structured `AdvisoryExtract`.
    """
    messages = build_image_messages(image)
    try:
        response = await client.chat.completions.create(
            model=VISION_MODEL,
            messages=messages,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name":   "AdvisoryExtract",
                    "strict": True,
                    "schema": _strict_schema(AdvisoryExtract),
                },
            },
            temperature=0.1,
            max_tokens=1024,
        )
    except Exception as exc:  # noqa: BLE001 — surface a learner-friendly hint
        raise RuntimeError(
            f"Vision request failed with model '{VISION_MODEL}'. Ensure the model "
            f"is vision-capable (set OPENAI_VISION_MODEL). Original error: {exc}"
        ) from exc

    _track(response)
    data = json.loads(response.choices[0].message.content)
    data["source_type"] = "image"
    return AdvisoryExtract.model_validate(data)


# ─── PDF INPUT ────────────────────────────────────────────────────────────────

def extract_pdf_text(pdf: str, page_cap: int = PDF_PAGE_CAP) -> str:
    """Extract text from the first `page_cap` pages of a PDF.

    Isolated so tests can stub it. Raises a clear error if `pypdf` is missing.
    """
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError(
            "PDF parsing requires 'pypdf'. Install the extra:  pip install -e '.[multimodal]'"
        ) from exc

    path = Path(pdf)
    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf}")

    reader = PdfReader(str(path))
    pages  = reader.pages[:page_cap]
    return "\n\n".join((page.extract_text() or "") for page in pages).strip()


async def extract_from_pdf(pdf: str) -> AdvisoryExtract:
    """Parse a PDF advisory to text, then extract a structured `AdvisoryExtract`."""
    text = extract_pdf_text(pdf)
    if not text:
        raise ValueError(
            "No extractable text found in the PDF (it may be a scanned image — "
            "use the --image path for image-only documents)."
        )

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": (
            f"{EXTRACT_INSTRUCTION}\n\n--- ADVISORY TEXT ---\n{text}"
        )},
    ]
    response = await client.chat.completions.create(
        model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        messages=messages,
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name":   "AdvisoryExtract",
                "strict": True,
                "schema": _strict_schema(AdvisoryExtract),
            },
        },
        temperature=0.1,
        max_tokens=1024,
    )

    _track(response)
    data = json.loads(response.choices[0].message.content)
    data["source_type"] = "pdf"
    return AdvisoryExtract.model_validate(data)


# ─── PRESENTATION ─────────────────────────────────────────────────────────────

def _render(extract: AdvisoryExtract) -> None:
    table = Table(box=box.ROUNDED, show_header=False)
    table.add_column("field", style="cyan", no_wrap=True)
    table.add_column("value")
    table.add_row("Source",   extract.source_type)
    table.add_row("CVE",      extract.cve_id or "—")
    table.add_row("Product",  extract.affected_product or "—")
    table.add_row("Severity", extract.claimed_severity or "—")
    for field in extract.extracted_fields:
        table.add_row(field.name, field.value)
    console.print(Panel(table, title="Advisory Extract", border_style="green"))

    if extract.grounding_quotes:
        quotes = "\n".join(f"  • {q}" for q in extract.grounding_quotes)
        console.print(Panel(quotes, title="Grounding quotes", border_style="dim"))

    u = get_usage()
    console.print(
        f"[dim]tokens: {u['total_tokens']}  ·  est. cost: ${u['estimated_cost_usd']}[/dim]"
    )


# ─── CLI ──────────────────────────────────────────────────────────────────────

async def _main() -> None:
    parser = argparse.ArgumentParser(description="VIGIL L4b — multimodal advisory extraction")
    group  = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--image", help="Image URL or local path (advisory screenshot)")
    group.add_argument("--pdf",   help="Local path to a PDF advisory/bulletin")
    args = parser.parse_args()

    _reset_usage()
    if args.image:
        console.print(f"[dim]Reading image: {args.image}[/dim]")
        extract = await extract_from_image(args.image)
    else:
        console.print(f"[dim]Reading PDF: {args.pdf}[/dim]")
        extract = await extract_from_pdf(args.pdf)

    _render(extract)


if __name__ == "__main__":
    asyncio.run(_main())
