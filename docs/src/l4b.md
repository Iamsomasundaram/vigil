---
title: "L4b: Multimodal"
summary: Read advisory screenshots and PDFs and extract structured, auditable data from them.
section: Levels
order: 6
---

# Level 4b: Multimodal

**The question this level answers:** what if the information I need is in a picture or a PDF, not in text or an API?

Every other level is text only. Real security work is not. A vendor advisory arrives as a screenshot pasted into a ticket. A patch bulletin is a PDF. L4b lets the model read these directly and pull out the CVE ID, the product and the claimed severity.

## The idea in plain English

Instead of asking a person to retype an advisory, you show it to the model and ask it to fill in a form. Then you ask it to **quote the lines it used**, so a person can check the extraction against the source.

{{flow: Image or PDF ~ the advisory | Prepare ~ encode the image, or extract PDF text | Model ~ fills the form | AdvisoryExtract ~ plus grounding quotes}}

This level has two separate paths because images and PDFs reach the model differently.

## Idea 1: a message whose content is a list of parts

Until now a message's `content` was a string. For images it becomes a **list of typed parts**:

```python
{"role": "user", "content": [
    {"type": "text",      "text": "Extract the advisory fields."},
    {"type": "image_url", "image_url": {"url": "https://.../advisory.png"}},
]}
```

A web address is passed straight through. A **local file** cannot be reached by the model's servers, so the code reads the bytes and sends them inside the message as a base64 data URI. Here is the function that decides which case it is:

{{include levels/l4b_multimodal.py#_image_url_part}}

Remote URLs and data URIs pass through untouched. A local path is read, its type is guessed from the file name, and the bytes are encoded. A missing file raises a clear `FileNotFoundError` instead of a confusing API error.

## Idea 2: the form to fill in

The result is typed, like earlier levels. The shape lives in `vigil/models.py`:

{{include vigil/models.py#AdvisoryExtract}}

Two design choices matter:

- The identity fields are **nullable** (`str | None`). A screenshot may not state every value, and the instructions tell the model to set a missing field to null rather than guess. A form that forces an answer invites invented ones.
- `grounding_quotes` holds the exact phrases the model relied on. This is **visual grounding**: the extraction stays traceable to the source instead of being a confident summary you cannot check.

## The instructions that enforce honesty

{{include levels/l4b_multimodal.py#SYSTEM_PROMPT}}

"Read ONLY what is shown" and "do not add facts from training memory" are the point of the level. Without them a model happily fills gaps from what it remembers about a famous CVE, which defeats the purpose of reading the document.

## The image path

{{include levels/l4b_multimodal.py#extract_from_image}}

Follow it step by step:

1. `build_image_messages` builds the system prompt plus a user message with a text part and an image part. It is separate from the network call so tests can check the message shape offline.
2. The call asks for `AdvisoryExtract` as a JSON schema, as in [Level 1](l1.md).
3. If the call fails, the error is wrapped with a hint to use a **vision-capable** model. The model name comes from `OPENAI_VISION_MODEL`, falling back to `OPENAI_MODEL` and then `gpt-4o-mini`.
4. The code sets `source_type` to `"image"` after the model replies, so provenance is recorded by your code, not by the model.

## The PDF path

For PDFs the code does **not** send the file to the model. It extracts the text first, then sends the text:

{{include levels/l4b_multimodal.py#extract_pdf_text}}

Then `extract_from_pdf` sends that text under a `--- ADVISORY TEXT ---` marker with the same system prompt, and sets `source_type` to `"pdf"`. Details worth knowing:

- PDF reading uses the optional `pypdf` package. If it is missing, you get an error telling you to install the extra: `pip install -e ".[multimodal]"`.
- Only the first **8 pages** are read by default, to cap cost on large bulletins. Set `VIGIL_PDF_PAGE_CAP` to change that.
- If no text can be extracted, the code stops with an error explaining the PDF may be a scan, and suggests the image path instead. A scanned PDF is a picture of text, so a text extractor finds nothing.

> **Note** This is an example of **graceful degradation**: when something is unavailable, the code fails with a clear, actionable message instead of a stack trace.

## Run it

The repository does not ship sample advisories, so use your own screenshot or PDF of a public advisory. You choose exactly one input:

```bash
python levels/l4b_multimodal.py --image path/to/advisory.png
python levels/l4b_multimodal.py --image https://example.com/advisory.png
python levels/l4b_multimodal.py --pdf path/to/bulletin.pdf
```

The program prints which file it is reading, then an **Advisory Extract** table (source, CVE, product, severity and any extra fields), then a **Grounding quotes** panel, then the token count and an estimated cost. I have not run it on a real advisory here, so I cannot show output.

The offline tests in `tests/test_multimodal.py` cover the message shape for URLs and local files, the missing-file error, and the missing `pypdf` case, all without calling the model.

> **Warning** Never feed an advisory you are not allowed to share to a hosted model. The image or text leaves your machine and goes to the provider. Redact anything sensitive first.

## Try it

> **Try it** 1) Run the same screenshot with the `grounding_quotes` instruction removed from `EXTRACT_INSTRUCTION` and see how much harder the result is to verify. 2) Give it a screenshot that does not mention a CVE ID and check that `cve_id` comes back empty instead of invented. 3) Set `VIGIL_PDF_PAGE_CAP=1` and compare what is extracted from a multi-page PDF.

## Common mistakes

- **Using a model without vision.** The image path needs a vision-capable model.
- **Trusting the extraction.** Compare the quotes with the source, especially for the CVE ID and severity.
- **Sending a scanned PDF down the PDF path.** There is no text to extract; use the image path.
- **Forgetting cost.** Images and long PDFs use many tokens. The page cap exists for a reason.
- **Leaking sensitive documents.** The content is sent to an external service.

## Check yourself

??? How does a local image reach the model?
    The code reads the file, base64-encodes it, and sends it as a data URI inside an `image_url` part of the message.

??? Why are the `cve_id` and `affected_product` fields nullable?
    The document may not state them, and the instructions say to leave a missing field empty rather than guess.

??? Why are PDFs converted to text first?
    In this level the PDF path extracts the text with `pypdf` and sends that text to the model, instead of sending the file.

??? What are grounding quotes for?
    They let a person check each extracted value against the exact source lines the model relied on.

Next: [Level 5](l5.md) gives the system a memory, so it can recall earlier analyses.
