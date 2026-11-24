"""
VIGIL Foundations F4 — Tokenization & Context Economics
"""

from __future__ import annotations

import argparse
import os
from typing import Any

from rich.console import Console
from rich.table import Table

from vigil.pricing import budget_report

console = Console()
MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")


def _get_encoding(model: str):
    import tiktoken

    try:
        return tiktoken.encoding_for_model(model)
    except Exception:
        return tiktoken.get_encoding("cl100k_base")


def count_tokens(text: str, model: str = MODEL) -> int:
    """Return the exact tiktoken count for text/model."""
    enc = _get_encoding(model)
    return len(enc.encode(text))


def sample_tokens(text: str, model: str = MODEL, limit: int = 16) -> list[str]:
    """Decode the first N token pieces so learners can inspect BPE boundaries."""
    enc = _get_encoding(model)
    ids = enc.encode(text)
    pieces: list[str] = []
    for tok in ids[:limit]:
        pieces.append(enc.decode([tok]))
    return pieces


def show_tokens(text: str, model: str = MODEL, limit: int = 32) -> list[dict[str, Any]]:
    """Return token ids + decoded pieces for inspection."""
    enc = _get_encoding(model)
    ids = enc.encode(text)
    rows: list[dict[str, Any]] = []
    for i, tok in enumerate(ids[:limit]):
        rows.append({"i": i, "id": tok, "piece": enc.decode([tok])})
    return rows


def tokenize_report(text: str, model: str = MODEL, completion_tokens_estimate: int = 0) -> dict[str, Any]:
    """Build a budget/cost report for one text snippet."""
    report = budget_report(
        model=model,
        prompt_tokens=count_tokens(text, model=model),
        completion_tokens=completion_tokens_estimate,
    )
    return {
        "model": model,
        "text_preview": (text[:120] + "...") if len(text) > 120 else text,
        "token_count": report["prompt_tokens"],
        "context_limit": report["context_limit"],
        "pct_of_context": report["pct_of_context"],
        "est_cost_usd": report["estimated_cost_usd"],
        "sample_tokens": sample_tokens(text, model=model),
    }


def render_token_table(rows: list[dict[str, Any]]) -> None:
    table = Table(title="Token breakdown")
    table.add_column("#")
    table.add_column("Token ID")
    table.add_column("Decoded piece")
    for r in rows:
        table.add_row(str(r["i"]), str(r["id"]), repr(r["piece"]))
    console.print(table)


def main() -> None:
    parser = argparse.ArgumentParser(description="F4 tokenization demo")
    parser.add_argument("text", nargs="*", default=["CVE-2021-44228 RCE in Log4j"])
    parser.add_argument("--model", default=MODEL)
    args = parser.parse_args()

    text = " ".join(args.text).strip()
    if not text:
        text = "CVE-2021-44228"

    report = tokenize_report(text, model=args.model)
    console.print(report)
    render_token_table(show_tokens(text, model=args.model))


if __name__ == "__main__":
    main()
