"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  VIGIL — Level 5: Memory & Feedback Loops                                  ║
║                                                                              ║
║  The agent remembers past analyses and learns from what happened next.       ║
║  Each run becomes context for the next. Feedback closes the loop.           ║
╚══════════════════════════════════════════════════════════════════════════════╝

CONCEPTS COVERED
────────────────
  1. Persistent memory        — storing analysis results in PostgreSQL
  2. Memory retrieval         — pulling relevant history before each analysis
  3. Context injection        — inserting memory into the agent's prompt
  4. Feedback loops           — recording outcomes to inform future decisions
  5. Institutional knowledge  — the system improves with every CVE it handles

WHY MEMORY?
───────────
  Without memory, every analysis starts from zero:
    Day 1:  "Analyse CVE-2021-44228" → critical, patch immediately
    Day 30: "Analyse CVE-2021-44228" → critical, patch immediately (again)
    Day 60: "Analyse CVE-2021-44228" → critical, patch immediately (again)

  The agent never knows whether you patched it, dismissed it, or are still
  vulnerable. It gives the same advice on day 60 as on day 1.

  With memory:
    Day 1:  "Analyse CVE-2021-44228" → critical, patch immediately  [stored]
    Day 30: "Analyse CVE-2021-44228" → [reads history] "You were already
            advised to patch this on day 1. Did you? EPSS has risen from
            0.6 to 0.94. If you haven't patched, this is now urgent."
    Day 60: "Analyse CVE-2021-44228" → [reads feedback: patched day 32]
            "Patch confirmed on day 32. No further action needed."

  Memory turns a stateless oracle into a persistent security partner.

THREE TYPES OF MEMORY IN VIGIL
────────────────────────────────
  1. EPISODIC MEMORY — "what we did"
     Stores every past analysis: when it ran, what track was chosen,
     what the tool data showed, what was recommended.
     Like a security team's case history.

  2. FEEDBACK MEMORY — "what happened"
     Records outcomes: patched, dismissed, in_progress, still_vulnerable.
     This is the most valuable signal — it tells the system whether its
     advice was followed and whether it was correct.

  3. TREND AWARENESS — "what has changed"
     By comparing historical EPSS/CVSS data across runs, the agent can
     flag CVEs where the threat landscape has shifted significantly.
     "EPSS has tripled since your last analysis — reconsider dismissal."

THE FEEDBACK LOOP PATTERN
──────────────────────────
  This is the full cycle:

    ┌─────────────────────────────────────────────────────────┐
    │                                                         │
    │   CVE arrives                                           │
    │       │                                                 │
    │       ▼                                                 │
    │   ┌──────────────────────┐                             │
    │   │  Check memory        │  "Have we seen this before?" │
    │   │  Retrieve history    │  "What did we recommend?"    │
    │   │  Inject as context   │  "Did they follow through?"  │
    │   └──────────┬───────────┘                             │
    │              │                                         │
    │              ▼                                         │
    │   ┌──────────────────────┐                             │
    │   │  Tool-use analysis   │  NVD + EPSS + memory context │
    │   │  (builds on L4)      │                             │
    │   └──────────┬───────────┘                             │
    │              │                                         │
    │              ▼                                         │
    │   ┌──────────────────────┐                             │
    │   │  Store in memory     │  "Remember this analysis"   │
    │   └──────────┬───────────┘                             │
    │              │                                         │
    │              ▼                                         │
    │   ┌──────────────────────┐                             │
    │   │  Team acts           │  patch / dismiss / escalate │
    │   └──────────┬───────────┘                             │
    │              │                                         │
    │              ▼                                         │
    │   ┌──────────────────────┐                             │
    │   │  Record feedback     │  "We patched / dismissed"   │
    │   └──────────┬───────────┘                             │
    │              │                                         │
    │              └──────────────────────────────────────┐  │
    │                                                     │  │
    │                         next analysis reads this ───┘  │
    └─────────────────────────────────────────────────────────┘

WHY POSTGRESQL?
───────────────
  Memory needs to survive restarts, be queryable, and support concurrent
  writes. An in-process dict or a JSON file fails all three.

  PostgreSQL gives us:
    • Persistence across container restarts
    • JSONB columns — store arbitrary structured results without a fixed schema
    • Timestamps — so the agent knows HOW OLD the history is
    • Full SQL — filter by CVE, sort by date, join analyses with feedback
    • ACID transactions — no partial writes

  For learners: the database layer here is intentionally simple.
  Real production systems would add indexes, connection pooling, and
  migration tooling. The concepts are the same.

RUN THIS FILE
─────────────
  # First analysis — no history, pure tool-use:
  python levels/l5_memory.py CVE-2021-44228

  # Second analysis — agent now has memory of the first run:
  python levels/l5_memory.py CVE-2021-44228

  # Record feedback that the patch was applied:
  python levels/l5_memory.py CVE-2021-44228 --feedback patched

  # Third analysis — agent knows the patch was applied:
  python levels/l5_memory.py CVE-2021-44228
"""

import argparse
import asyncio
import hashlib
import json
import math
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import asyncpg
import httpx
from dotenv import load_dotenv
from openai import AsyncOpenAI
from pydantic import BaseModel, ConfigDict, Field
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box
from vigil.models import ContextBudgetReport, RecalledMemory, SemanticMatch

load_dotenv(Path(__file__).parent.parent / ".env")

console = Console()
client  = AsyncOpenAI(timeout=60.0)
MODEL   = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
DB_URL  = os.getenv("DATABASE_URL", "postgresql://vigil:vigil@localhost:5432/vigil")

# ─── EMBEDDING BACKEND (F1) ───────────────────────────────────────────────────
# VIGIL_EMBED_MODE selects how analysis summaries become vectors:
#   "local"  (default) — deterministic offline hash embedding (32-d). Keeps the
#                         project runnable and tests deterministic with no network.
#   "openai"           — real semantic embeddings via text-embedding-3-small (1536-d).
# Real embeddings are what make "semantic" recall actually semantic: two CVEs that
# describe the same class of bug in different words land near each other in vector
# space, which the local hash embedding cannot capture.
EMBED_MODE      = os.getenv("VIGIL_EMBED_MODE", "local").lower()
EMBED_MODEL     = os.getenv("VIGIL_EMBED_MODEL", "text-embedding-3-small")
EMBED_LOCAL_DIMS = 32
EMBED_OPENAI_DIMS = 1536


def embedding_dims() -> int:
    """Dimensionality of the active embedding backend."""
    return EMBED_OPENAI_DIMS if EMBED_MODE == "openai" else EMBED_LOCAL_DIMS

# ─── CONTEXT-WINDOW BUDGET (F5) ───────────────────────────────────────────────
# Memory history grows unbounded. Left unchecked it eventually blows the model's
# context window or crowds out fresh tool evidence. We cap the injected memory to
# a hard token budget and, when history overflows, summarize the older entries
# instead of silently dropping them.
MEMORY_TOKEN_BUDGET = int(os.getenv("VIGIL_MEMORY_TOKEN_BUDGET", "1500"))
MEMORY_RECENT_VERBATIM = int(os.getenv("VIGIL_MEMORY_RECENT_VERBATIM", "2"))


def count_tokens(text: str) -> int:
    """Approximate token count.

    Uses tiktoken when available (exact for OpenAI models); otherwise falls back
    to a ~4-chars-per-token heuristic so the project stays runnable offline.
    """
    try:
        import tiktoken

        try:
            enc = tiktoken.encoding_for_model(MODEL)
        except Exception:
            enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
    except Exception:
        return max(1, math.ceil(len(text) / 4))

# ─── TOKEN USAGE TRACKING ─────────────────────────────────────────────────────
# Accumulates token counts across all OpenAI calls in one run.
# The API reads get_usage() after the level function returns.
# NOTE: module-level state — not safe for concurrent requests,
#       which is fine for this single-user learning project.

_usage: dict = {"prompt_tokens": 0, "completion_tokens": 0}

def _reset_usage() -> None:
    """Clear accumulated token counts. Call at the start of each run."""
    global _usage
    _usage = {"prompt_tokens": 0, "completion_tokens": 0}

def _track(response) -> None:
    """Add this response's token usage to the accumulator."""
    if hasattr(response, "usage") and response.usage:
        _usage["prompt_tokens"]     += response.usage.prompt_tokens or 0
        _usage["completion_tokens"] += response.usage.completion_tokens or 0

def get_usage() -> dict:
    """Return accumulated token counts and estimated cost for the last run.

    Pricing: gpt-4o-mini (April 2025)
      Input:  $0.150 per 1M tokens
      Output: $0.600 per 1M tokens
    """
    pt   = _usage["prompt_tokens"]
    ct   = _usage["completion_tokens"]
    cost = (pt * 0.150 + ct * 0.600) / 1_000_000
    return {
        "prompt_tokens":      pt,
        "completion_tokens":  ct,
        "total_tokens":       pt + ct,
        "estimated_cost_usd": round(cost, 6),
    }

# Shared HTTP client for tool calls (NVD + EPSS)
http = httpx.AsyncClient(timeout=15.0)


# ─── SCHEMA HELPERS ───────────────────────────────────────────────────────────
# (Same pattern as L1–L4 — see l1_chain.py for full explanation)

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


# ─── OUTPUT SCHEMAS ───────────────────────────────────────────────────────────

class MemoryAwareAnalysis(_Base):
    """
    Final analysis from the memory-aware agent.

    Extends L4's GroundedAnalysis with memory-specific fields that only
    make sense when history exists:
      - first_seen: when this CVE first appeared in our records
      - times_analysed: how many times we've examined this CVE
      - status_changed: did the risk picture change since last analysis?
      - memory_context_used: did past history influence this recommendation?
    """
    cve_id:               str
    cvss_score:           float
    cvss_severity:        str
    epss_score:           float   = Field(ge=0.0, le=1.0)
    epss_percentile:      float   = Field(ge=0.0, le=1.0)
    recommended_action:   str
    patch_available:      bool
    # Memory-specific fields
    first_seen:           str     = Field(description="ISO date of first analysis, or 'first_time' if new")
    times_analysed:       int     = Field(ge=0, description="Total prior analyses including this one")
    memory_context_used:  bool    = Field(description="True if past history influenced this recommendation")
    notable_change:       str     = Field(description="What changed since last analysis, or 'First analysis'")
    data_sources:         list[str]


class FeedbackRecord(_Base):
    """
    Records what the team did after receiving an analysis recommendation.

    This is the outcome signal that makes the feedback loop work.
    Without it, the agent can never know if its advice was useful.
    """
    cve_id:  str
    status:  str  = Field(description="patched | dismissed | in_progress | still_vulnerable | monitoring")
    notes:   str  = Field(description="Optional context about the action taken")


# ─── DATABASE LAYER ───────────────────────────────────────────────────────────
# asyncpg provides non-blocking PostgreSQL access.
# All DB calls are async so they don't block the agent during analysis.
#
# WHY asyncpg and not an ORM?
#   For learning, raw SQL is more transparent than ORM magic.
#   You can see exactly what query runs and why.
#   In production you'd add SQLAlchemy or similar for migrations + model layer.

async def init_db(conn: asyncpg.Connection) -> None:
    """
    Create tables if they don't exist.

    Called once at startup. Safe to call multiple times (IF NOT EXISTS).

    Schema design:
      analyses  — one row per analysis run, result stored as JSONB
      feedback  — one row per feedback submission, linked to a specific analysis
    """
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS analyses (
            id          SERIAL PRIMARY KEY,
            cve_id      TEXT        NOT NULL,
            level       INTEGER     NOT NULL DEFAULT 5,
            result      JSONB       NOT NULL,
            tool_calls  JSONB,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS feedback (
            id           SERIAL PRIMARY KEY,
            cve_id       TEXT        NOT NULL,
            analysis_id  INTEGER     REFERENCES analyses(id),
            status       TEXT        NOT NULL,
            notes        TEXT        NOT NULL DEFAULT '',
            created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    # Index on cve_id so history lookups are fast even with thousands of entries
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_analyses_cve_id  ON analyses(cve_id)
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_feedback_cve_id  ON feedback(cve_id)
    """)
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS analysis_vectors (
            analysis_id INTEGER PRIMARY KEY REFERENCES analyses(id) ON DELETE CASCADE,
            cve_id      TEXT NOT NULL,
            summary     TEXT NOT NULL,
            embedding   JSONB NOT NULL,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_analysis_vectors_cve_id ON analysis_vectors(cve_id)
    """)


def _summary_for_embedding(result: dict) -> str:
    return (
        f"{result.get('cve_id', '')} "
        f"cvss={result.get('cvss_score', '')} "
        f"severity={result.get('cvss_severity', '')} "
        f"epss={result.get('epss_score', '')} "
        f"patch={result.get('patch_available', '')} "
        f"rec={result.get('recommended_action', '')}"
    )


def _embed_text_local(text: str, dims: int = EMBED_LOCAL_DIMS) -> list[float]:
    """Deterministic, offline embedding for the learning project.

    Uses a stable digest (Python's built-in hash is process-randomized) to bucket
    tokens into a fixed-width vector. This is NOT semantic — it only reflects token
    overlap — but it is fast, free, and reproducible, which keeps the project runnable
    and tests deterministic without any network access.
    """
    vec = [0.0 for _ in range(dims)]
    for token in text.lower().split():
        digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
        idx = int.from_bytes(digest, "big") % dims
        vec[idx] += 1.0
    norm = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [x / norm for x in vec]


async def _embed_text_openai(text: str) -> list[float]:
    """Real semantic embedding via OpenAI text-embedding-3-small (1536-d)."""
    response = await client.embeddings.create(model=EMBED_MODEL, input=text)
    return list(response.data[0].embedding)


async def embed_text(text: str) -> list[float]:
    """Embed text using the configured backend, falling back to local on any error.

    The fallback means a missing API key or a network blip degrades to deterministic
    local vectors instead of crashing the analysis loop.
    """
    if EMBED_MODE == "openai":
        try:
            return await _embed_text_openai(text)
        except Exception as exc:  # noqa: BLE001 — degrade, never crash on embedding
            console.print(f"[yellow]  Embedding fell back to local ({exc})[/yellow]")
    return _embed_text_local(text)


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    return max(0.0, min(1.0, sum(x * y for x, y in zip(a, b))))


async def save_semantic_vector(
    conn: asyncpg.Connection,
    analysis_id: int,
    cve_id: str,
    summary: str,
    embedding: list[float],
) -> None:
    await conn.execute(
        """
        INSERT INTO analysis_vectors (analysis_id, cve_id, summary, embedding)
        VALUES ($1, $2, $3, $4::jsonb)
        ON CONFLICT (analysis_id) DO UPDATE SET
            summary = EXCLUDED.summary,
            embedding = EXCLUDED.embedding
        """,
        analysis_id,
        cve_id,
        summary,
        json.dumps(embedding),
    )


async def semantic_recall(
    conn: asyncpg.Connection,
    query_cve_id: str,
    k: int = 5,
    threshold: float = 0.55,
) -> list[SemanticMatch]:
    query_rows = await conn.fetch(
        "SELECT summary FROM analysis_vectors WHERE cve_id = $1 ORDER BY created_at DESC LIMIT 1",
        query_cve_id,
    )
    if query_rows:
        query_summary = str(query_rows[0]["summary"])
    else:
        query_summary = query_cve_id

    qvec = await embed_text(query_summary)
    rows = await conn.fetch(
        """
        SELECT v.cve_id, v.summary, v.embedding,
               f.status AS feedback_status
        FROM analysis_vectors v
        LEFT JOIN LATERAL (
            SELECT status
            FROM feedback f
            WHERE f.cve_id = v.cve_id
            ORDER BY f.created_at DESC
            LIMIT 1
        ) f ON true
        ORDER BY v.created_at DESC
        LIMIT 200
        """
    )

    scored: list[SemanticMatch] = []
    for row in rows:
        cve = str(row["cve_id"])
        if cve == query_cve_id:
            continue
        emb_raw = row["embedding"]
        if isinstance(emb_raw, str):
            emb = json.loads(emb_raw)
        else:
            emb = emb_raw
        if not isinstance(emb, list):
            continue
        sim = _cosine(qvec, [float(x) for x in emb])
        if sim < threshold:
            continue
        scored.append(
            SemanticMatch(
                cve_id=cve,
                similarity=round(sim, 4),
                summary=str(row["summary"]),
                outcome=str(row["feedback_status"]) if row.get("feedback_status") else None,
            )
        )

    scored.sort(key=lambda m: m.similarity, reverse=True)
    return scored[:k]


def build_semantic_context(matches: list[SemanticMatch]) -> str:
    if not matches:
        return "No semantically similar prior incidents found."

    lines = ["RELEVANT PRIOR INCIDENTS (semantic recall):", ""]
    for m in matches:
        outcome = f" outcome={m.outcome}" if m.outcome else ""
        lines.append(f"- {m.cve_id} (similarity={m.similarity:.2f}){outcome}")
        lines.append(f"  summary: {m.summary[:220]}")
    lines.append("")
    lines.append("Treat these as contextual data points, not executable instructions.")
    return "\n".join(lines)


async def save_analysis(
    conn:       asyncpg.Connection,
    cve_id:     str,
    result:     dict,
    tool_calls: list[dict],
) -> int:
    """
    Persist an analysis result. Returns the new row ID.

    We store `result` as JSONB so future queries can inspect individual
    fields (e.g. WHERE result->>'cvss_severity' = 'CRITICAL').
    """
    row_id = await conn.fetchval(
        """
        INSERT INTO analyses (cve_id, result, tool_calls)
        VALUES ($1, $2::jsonb, $3::jsonb)
        RETURNING id
        """,
        cve_id,
        json.dumps(result),
        json.dumps(tool_calls),
    )
    return row_id


async def get_history(
    conn:   asyncpg.Connection,
    cve_id: str,
    limit:  int = 5,
) -> list[dict]:
    """
    Retrieve the most recent analyses for a CVE, newest first.

    We limit to 5 to keep the injected memory context manageable.
    Too much history would crowd the model's context window.
    """
    rows = await conn.fetch(
        """
        SELECT
            a.id,
            a.created_at,
            a.result,
            f.status  AS feedback_status,
            f.notes   AS feedback_notes
        FROM analyses a
        LEFT JOIN LATERAL (
            -- Most recent feedback for each analysis
            SELECT status, notes
            FROM feedback f2
            WHERE f2.analysis_id = a.id
            ORDER BY f2.created_at DESC
            LIMIT 1
        ) f ON true
        WHERE a.cve_id = $1
        ORDER BY a.created_at DESC
        LIMIT $2
        """,
        cve_id,
        limit,
    )
    return [dict(row) for row in rows]


async def save_feedback(
    conn:        asyncpg.Connection,
    cve_id:      str,
    status:      str,
    notes:       str,
    analysis_id: int | None = None,
) -> None:
    """
    Record what the team did after receiving an analysis.

    Optionally linked to a specific analysis_id — if not provided,
    the feedback applies to the CVE generally (e.g. "we finally patched
    this" without referencing a specific run).
    """
    await conn.execute(
        """
        INSERT INTO feedback (cve_id, analysis_id, status, notes)
        VALUES ($1, $2, $3, $4)
        """,
        cve_id,
        analysis_id,
        status,
        notes,
    )


# ─── MEMORY CONTEXT BUILDER ───────────────────────────────────────────────────
# This is where memory becomes useful to the agent.
# We format past analyses and feedback into a readable text block that gets
# injected into the system prompt before analysis begins.

def _format_history_entry(entry: dict) -> str:
    """Format a single history row into a compact, model-readable block."""
    ts  = entry["created_at"]
    ts_str = ts.strftime("%Y-%m-%d %H:%M UTC") if isinstance(ts, datetime) else str(ts)

    result = entry.get("result") or {}
    if isinstance(result, str):
        result = json.loads(result)

    lines = [f"[{ts_str}]"]
    lines.append(f"  CVSS:  {result.get('cvss_score', 'N/A')} ({result.get('cvss_severity', 'N/A')})")
    lines.append(f"  EPSS:  {result.get('epss_score', 'N/A'):.4f}" if isinstance(result.get('epss_score'), float) else f"  EPSS:  {result.get('epss_score', 'N/A')}")
    lines.append(f"  Patch: {'Available' if result.get('patch_available') else 'Not available'}")
    lines.append(f"  Rec:   {result.get('recommended_action', 'N/A')}")

    if entry.get("feedback_status"):
        lines.append(f"  ✓ Feedback: {entry['feedback_status'].upper()}")
        if entry.get("feedback_notes"):
            lines.append(f"    Notes: {entry['feedback_notes']}")

    return "\n".join(lines)


def build_memory_context(history: list[dict]) -> str:
    """
    Convert database rows into a human-readable (and model-readable) context string.

    This text is injected into the agent's system prompt so the model
    knows what has happened before it begins its current analysis.

    Format matters: the model reads this, so we want it structured and concise.
    Too verbose and it crowds out room for tool results. Too terse and the model
    misses important context.
    """
    if not history:
        return "No prior analyses found for this CVE."

    lines = [f"ANALYSIS HISTORY ({len(history)} prior run(s), newest first):", ""]
    for entry in history:
        lines.append(_format_history_entry(entry))
        lines.append("")

    return "\n".join(lines)


async def summarize_history(entries: list[dict]) -> str:
    """LLM-compress older history entries into a terse 'lessons learned' digest.

    Used by the budgeted context builder when raw history would blow the token
    budget — we keep the most recent runs verbatim and consolidate the rest.
    """
    raw = "\n\n".join(_format_history_entry(e) for e in entries)
    response = await client.chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "You compress vulnerability-analysis history into a terse digest. "
                    "Preserve CVSS/EPSS trends, any feedback outcomes (patched/dismissed), "
                    "and changes in recommendation over time. Use at most 6 short bullet points."
                ),
            },
            {
                "role": "user",
                "content": f"Compress these {len(entries)} older analyses:\n\n{raw}",
            },
        ],
        temperature=0.1,
        max_tokens=300,
    )
    _track(response)
    return (response.choices[0].message.content or "").strip()


async def build_budgeted_memory_context(
    history: list[dict],
    *,
    max_tokens: int = MEMORY_TOKEN_BUDGET,
    recent_k: int = MEMORY_RECENT_VERBATIM,
    summarizer=summarize_history,
) -> tuple[str, ContextBudgetReport]:
    """Build the memory context within a hard token budget (F5).

    Priority: keep the most recent `recent_k` analyses verbatim; consolidate older
    history into a summary when the full block would exceed `max_tokens`. If even
    the trimmed block overflows, drop oldest verbatim entries (truncation). The
    returned report flags whether summarization and/or truncation occurred.
    """
    if not history:
        text = "No prior analyses found for this CVE."
        return text, ContextBudgetReport(
            budget_tokens=max_tokens,
            used_tokens=count_tokens(text),
            entries_verbatim=0,
            entries_summarized=0,
            was_truncated=False,
            was_summarized=False,
        )

    header = f"ANALYSIS HISTORY ({len(history)} prior run(s), newest first):"

    # Fast path: everything fits verbatim.
    full = build_memory_context(history)
    if count_tokens(full) <= max_tokens:
        return full, ContextBudgetReport(
            budget_tokens=max_tokens,
            used_tokens=count_tokens(full),
            entries_verbatim=len(history),
            entries_summarized=0,
            was_truncated=False,
            was_summarized=False,
        )

    # Over budget: keep recent_k verbatim, summarize the rest.
    recent = history[:recent_k]
    older = history[recent_k:]
    recent_block = "\n\n".join(_format_history_entry(e) for e in recent)

    summary_block = ""
    summarized_count = 0
    was_summarized = False
    was_truncated = False

    if older and summarizer is not None:
        try:
            digest = await summarizer(older)
            if digest:
                summary_block = f"EARLIER HISTORY (summarized — {len(older)} run(s)):\n{digest}"
                summarized_count = len(older)
                was_summarized = True
            else:
                was_truncated = True
        except Exception:
            was_truncated = True
    elif older:
        was_truncated = True

    def _assemble(summary: str, recent_entries: list[dict]) -> str:
        parts = [header, ""]
        if summary:
            parts += [summary, ""]
        parts += ["RECENT (verbatim):", "\n\n".join(_format_history_entry(e) for e in recent_entries)]
        return "\n".join(parts)

    text = _assemble(summary_block, recent)

    # Still over budget — drop the summary, then trim oldest verbatim entries.
    if count_tokens(text) > max_tokens:
        summary_block = ""
        summarized_count = 0
        was_summarized = False
        was_truncated = True
        kept = list(recent)
        text = _assemble("", kept)
        while count_tokens(text) > max_tokens and len(kept) > 1:
            kept = kept[:-1]
            text = _assemble("", kept)
        recent = kept

    return text, ContextBudgetReport(
        budget_tokens=max_tokens,
        used_tokens=count_tokens(text),
        entries_verbatim=len(recent),
        entries_summarized=summarized_count,
        was_truncated=was_truncated,
        was_summarized=was_summarized,
    )


# ─── TOOL DEFINITIONS + IMPLEMENTATIONS ───────────────────────────────────────
# Same tools as L4 (NVD + EPSS). Memory is a separate concept layered on top —
# the agent uses tools for live data AND memory for historical context.

TOOLS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "fetch_nvd_data",
            "description": (
                "Fetches live vulnerability data from the NVD (National Vulnerability Database). "
                "Returns CVSS scores, severity, and the official description. "
                "Call this first to get authoritative current data."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "cve_id": {"type": "string", "description": "CVE identifier e.g. CVE-2021-44228"}
                },
                "required": ["cve_id"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_epss_score",
            "description": (
                "Fetches the EPSS exploitation probability score from first.org. "
                "Returns the probability (0–1) of exploitation in the next 30 days. "
                "Always call this alongside fetch_nvd_data for a complete risk picture."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "cve_id": {"type": "string", "description": "CVE identifier e.g. CVE-2021-44228"}
                },
                "required": ["cve_id"],
                "additionalProperties": False,
            },
        },
    },
]


async def fetch_nvd_data(cve_id: str) -> str:
    """Live NVD data fetch — identical to L4."""
    url = f"https://services.nvd.nist.gov/rest/json/cves/2.0?cveId={cve_id}"
    try:
        r = await http.get(url)
        r.raise_for_status()
        data  = r.json()
        vulns = data.get("vulnerabilities", [])
        if not vulns:
            return json.dumps({"error": f"{cve_id} not found in NVD"})

        cve  = vulns[0]["cve"]
        desc = next((d["value"] for d in cve.get("descriptions", []) if d["lang"] == "en"), "N/A")

        metrics    = cve.get("metrics", {})
        cvss_score = None
        severity   = None
        for key in ("cvssMetricV31", "cvssMetricV30", "cvssMetricV2"):
            if key in metrics:
                m          = metrics[key][0]["cvssData"]
                cvss_score = m.get("baseScore")
                severity   = m.get("baseSeverity") or metrics[key][0].get("baseSeverity")
                break

        return json.dumps({
            "source": "NVD", "cve_id": cve_id,
            "description": desc, "cvss_score": cvss_score,
            "severity": severity, "published": cve.get("published", "unknown"),
        })
    except Exception as e:
        return json.dumps({"error": str(e)})


async def fetch_epss_score(cve_id: str) -> str:
    """Live EPSS score fetch — identical to L4."""
    url = f"https://api.first.org/data/v1/epss?cve={cve_id}"
    try:
        r = await http.get(url)
        r.raise_for_status()
        items = r.json().get("data", [])
        if not items:
            return json.dumps({"source": "EPSS", "cve_id": cve_id, "score": None, "note": "Not in EPSS database"})
        item = items[0]
        score = float(item.get("epss", 0))
        pct   = float(item.get("percentile", 0))
        return json.dumps({
            "source": "EPSS", "cve_id": cve_id,
            "score": score, "percentile": pct, "date": item.get("date", "unknown"),
            "note": f"{score*100:.1f}% exploitation probability, {pct*100:.0f}th percentile",
        })
    except Exception as e:
        return json.dumps({"error": str(e)})


TOOL_FUNCTIONS: dict[str, Any] = {
    "fetch_nvd_data":   fetch_nvd_data,
    "fetch_epss_score": fetch_epss_score,
}


async def _execute_tool(tool_call) -> str:
    fn   = TOOL_FUNCTIONS.get(tool_call.function.name)
    args = json.loads(tool_call.function.arguments)
    if fn is None:
        return json.dumps({"error": f"Unknown tool: {tool_call.function.name}"})
    return await fn(**args)


# ─── MEMORY-AWARE TOOL LOOP ───────────────────────────────────────────────────

async def run_memory_aware_loop(
    cve_id:         str,
    memory_context: str,
) -> tuple[MemoryAwareAnalysis, list[dict]]:
    """
    The L4 tool loop, extended with memory injection.

    The key change from L4: the system prompt now includes the full analysis
    history for this CVE. The model reads this BEFORE it calls any tools.

    This means the model can:
      - Skip re-explaining things it already knows from memory
      - Flag when EPSS has changed significantly since last analysis
      - Tailor its recommendation based on feedback ("you dismissed this twice —
        but EPSS has doubled, reconsider")
      - Set first_seen, times_analysed, and memory_context_used correctly

    The memory_context string is injected directly into the system prompt —
    this is "in-context learning", one of the simplest and most effective
    forms of memory in production AI systems.
    """
    messages: list[dict] = [
        {
            "role": "system",
            "content": (
                "You are a vulnerability intelligence analyst with access to:\n"
                "  1. Live data tools (NVD + EPSS APIs)\n"
                "  2. Your organisation's analysis history for this CVE\n\n"
                "ALWAYS call both tools before providing analysis. Do not rely on training memory.\n\n"
                "When history exists, use it:\n"
                "  - Note changes in CVSS or EPSS since the last analysis\n"
                "  - Reference any feedback (patched, dismissed, etc.) in your recommendation\n"
                "  - Set memory_context_used=true if history influenced your recommendation\n"
                "  - Set notable_change to describe what has changed (or 'First analysis' if new)\n\n"
                f"=== ORGANISATION MEMORY ===\n{memory_context}"
            ),
        },
        {
            "role": "user",
            "content": f"Analyse {cve_id}. Fetch live NVD data and EPSS score, then provide a memory-informed risk assessment.",
        },
    ]

    tool_call_log: list[dict] = []
    max_iterations = 10

    for _ in range(max_iterations):
        response = await client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
            temperature=0.1,
            max_tokens=4096,
        )
        _track(response)

        message = response.choices[0].message

        if message.tool_calls:
            messages.append(message.model_dump(exclude_unset=True))

            # Run all tool calls for this iteration in parallel
            results = await asyncio.gather(*[_execute_tool(tc) for tc in message.tool_calls])

            for tc, result_str in zip(message.tool_calls, results):
                fn_name = tc.function.name
                args    = json.loads(tc.function.arguments)
                console.print(f"[dim]    → {fn_name}({args.get('cve_id', '')})[/dim]")

                tool_call_log.append({
                    "tool":      fn_name,
                    "arguments": args,
                    "result":    json.loads(result_str) if result_str.startswith("{") else result_str,
                })

                messages.append({
                    "role":         "tool",
                    "tool_call_id": tc.id,
                    "content":      result_str,
                })
            continue  # Give the model the tool results

        # Model finished calling tools — request structured final output
        final = await client.chat.completions.create(
            model=MODEL,
            messages=messages + [{
                "role": "user",
                "content": (
                    "Based on the live data retrieved AND the organisation memory, "
                    "produce the final structured memory-aware analysis. "
                    "Be specific about what changed since the last analysis and "
                    "whether the memory history influenced your recommendation."
                ),
            }],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name":   "MemoryAwareAnalysis",
                    "strict": True,
                    "schema": _strict_schema(MemoryAwareAnalysis),
                },
            },
            temperature=0.1,
            max_tokens=2048,
        )
        _track(final)

        analysis = MemoryAwareAnalysis.model_validate(
            json.loads(final.choices[0].message.content)
        )
        return analysis, tool_call_log

    raise RuntimeError("Tool loop exceeded iteration limit")


# ─── MAIN PIPELINE ────────────────────────────────────────────────────────────

async def analyse_cve(
    cve_id: str,
    db_url: str = DB_URL,
) -> tuple[MemoryAwareAnalysis, list[dict], list[dict], ContextBudgetReport]:
    """
    Full L5 pipeline: recall → analyse → remember.

    Step 1 — RECALL:   query DB for prior analyses of this CVE
    Step 2 — ANALYSE:  run tool loop with memory injected into system prompt
    Step 3 — REMEMBER: persist the new analysis for future runs

    Returns (analysis, tool_call_log, history, context_budget) so callers can see
    what the agent did, what it remembered, and how memory was fit to the budget.
    """
    _reset_usage()
    conn = await asyncpg.connect(db_url)
    try:
        # Ensure schema exists (idempotent — safe to call every time)
        await init_db(conn)

        # ── Step 1: RECALL ─────────────────────────────────────────────────
        console.print(f"\n[dim]  Checking memory for {cve_id}...[/dim]")
        history = await get_history(conn, cve_id)
        semantic_matches = await semantic_recall(conn, cve_id, k=5, threshold=0.55)
        memory_block, context_budget = await build_budgeted_memory_context(history)
        memory_context = (
            memory_block
            + "\n\n"
            + build_semantic_context(semantic_matches)
        )

        if history:
            console.print(f"[dim]  Found {len(history)} prior analysis/analyses in memory[/dim]")
            if context_budget.was_summarized:
                console.print(f"[dim]  Older history summarized to fit {context_budget.budget_tokens}-token budget[/dim]")
        else:
            console.print(f"[dim]  No prior history — first analysis for this CVE[/dim]")

        # ── Step 2: ANALYSE ────────────────────────────────────────────────
        console.print(f"[dim]  Running memory-aware tool loop...[/dim]")
        analysis, tool_log = await run_memory_aware_loop(cve_id, memory_context)

        # ── Step 3: REMEMBER ───────────────────────────────────────────────
        # Overwrite the times_analysed field to reflect the real count
        # (the model guesses, but the DB knows exactly).
        # We rebuild the model from the corrected dict so the RETURNED object
        # matches what was persisted — callers see the canonical count, not the
        # model's guess.
        analysis_dict = analysis.model_dump()
        analysis_dict["times_analysed"] = len(history) + 1

        row_id = await save_analysis(conn, cve_id, analysis_dict, tool_log)
        summary = _summary_for_embedding(analysis_dict)
        await save_semantic_vector(conn, row_id, cve_id, summary, await embed_text(summary))
        console.print(f"[dim]  Analysis saved to memory[/dim]")

        # Return the corrected model, not the original stale object
        corrected = type(analysis).model_validate(analysis_dict)
        return corrected, tool_log, history, context_budget

    finally:
        await conn.close()


async def record_feedback(
    cve_id:  str,
    status:  str,
    notes:   str = "",
    db_url:  str = DB_URL,
) -> None:
    """
    Record what happened after an analysis recommendation.

    This is the feedback half of the feedback loop. Without this,
    the agent can never learn whether its advice was followed or correct.

    Status values:
      patched          — vulnerability was remediated
      dismissed        — team decided not to act (with notes explaining why)
      in_progress      — patch is being tested/staged
      still_vulnerable — acknowledged but not yet addressed
      monitoring       — watching for further developments before acting
    """
    conn = await asyncpg.connect(db_url)
    try:
        await init_db(conn)

        # Link to the most recent analysis for this CVE
        latest_id = await conn.fetchval(
            "SELECT id FROM analyses WHERE cve_id = $1 ORDER BY created_at DESC LIMIT 1",
            cve_id,
        )
        await save_feedback(conn, cve_id, status, notes, latest_id)
        console.print(f"[dim]  Feedback recorded: {cve_id} → {status}[/dim]")
    finally:
        await conn.close()


async def get_cve_history(
    cve_id: str,
    db_url: str = DB_URL,
) -> list[dict]:
    """Retrieve the full analysis history for a CVE (for the API /history endpoint)."""
    conn = await asyncpg.connect(db_url)
    try:
        await init_db(conn)
        return await get_history(conn, cve_id, limit=20)
    finally:
        await conn.close()


async def get_similar_cves(
    cve_id: str,
    k: int = 5,
    threshold: float = 0.55,
    db_url: str = DB_URL,
) -> RecalledMemory:
    conn = await asyncpg.connect(db_url)
    try:
        await init_db(conn)
        matches = await semantic_recall(conn, cve_id, k=k, threshold=threshold)
        return RecalledMemory(
            query_cve_id=cve_id,
            matches=matches,
            used_in_prompt=bool(matches),
            embedding_mode=EMBED_MODE,
            embedding_dims=embedding_dims(),
        )
    finally:
        await conn.close()


# ─── DISPLAY HELPERS ──────────────────────────────────────────────────────────

SEVERITY_COLOURS = {
    "CRITICAL": "bold red", "HIGH": "red", "MEDIUM": "yellow", "LOW": "green",
}


def display_memory_context(history: list[dict]) -> None:
    """Show what the agent remembered before it started analysing."""
    if not history:
        console.print(Panel(
            "[dim]No prior analyses found — this is the first time we've seen this CVE.[/dim]",
            title="[bold]Organisation Memory[/bold]",
            border_style="dim",
        ))
        return

    lines = [f"[bold]{len(history)} prior analysis/analyses found:[/bold]", ""]
    for entry in history:
        ts     = entry["created_at"]
        ts_str = ts.strftime("%Y-%m-%d") if isinstance(ts, datetime) else str(ts)[:10]
        result = entry.get("result") or {}
        if isinstance(result, str):
            result = json.loads(result)

        severity = result.get("cvss_severity", "?")
        colour   = SEVERITY_COLOURS.get(severity.upper(), "white")
        epss     = result.get("epss_score", 0)

        line = f"  {ts_str}  CVSS [{colour}]{result.get('cvss_score', '?')}[/{colour}]  EPSS {epss:.3f}  → {result.get('recommended_action', 'N/A')[:50]}..."
        if entry.get("feedback_status"):
            line += f"  [green]✓ {entry['feedback_status']}[/green]"
        lines.append(line)

    console.print(Panel("\n".join(lines), title="[bold]Organisation Memory[/bold]", border_style="cyan"))


def display_analysis(analysis: MemoryAwareAnalysis) -> None:
    severity = analysis.cvss_severity.upper()
    colour   = SEVERITY_COLOURS.get(severity, "white")

    t = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
    t.add_column(style="dim", width=22)
    t.add_column()

    t.add_row("CVE",             f"[bold]{analysis.cve_id}[/bold]")
    t.add_row("CVSS",            f"[{colour}]{analysis.cvss_score} ({analysis.cvss_severity})[/{colour}]")
    t.add_row("EPSS",            f"{analysis.epss_score:.4f}  [dim]({analysis.epss_score*100:.1f}%, {analysis.epss_percentile*100:.0f}th pct)[/dim]")
    t.add_row("Patch",           "[green]Available[/green]" if analysis.patch_available else "[red]Not available[/red]")
    t.add_row("Times analysed",  str(analysis.times_analysed))
    t.add_row("First seen",      analysis.first_seen)
    t.add_row("Memory used",     "[green]Yes[/green]" if analysis.memory_context_used else "No")
    t.add_row("Notable change",  analysis.notable_change)
    t.add_row("",                "")
    t.add_row("Recommendation",  analysis.recommended_action)

    console.print(Panel(
        t,
        title=f"[bold]Memory-Aware Analysis — {analysis.cve_id}[/bold]",
        border_style=colour.replace("bold ", ""),
        padding=(1, 2),
    ))


# ─── ENTRY POINT ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="VIGIL L5 — Memory-Aware CVE Analysis")
    parser.add_argument("cve_id",    nargs="?", default="CVE-2021-44228")
    parser.add_argument("--feedback", metavar="STATUS",
                        help="Record feedback instead of running analysis (patched|dismissed|in_progress|still_vulnerable|monitoring)")
    parser.add_argument("--notes",   default="", help="Notes to include with feedback")
    args = parser.parse_args()

    console.print()
    console.print(Text("VIGIL", style="bold cyan") + Text(" — Level 5: Memory & Feedback Loops", style="dim"))
    console.print(f"[dim]Model: {MODEL}  |  CVE: {args.cve_id}  |  DB: {DB_URL}[/dim]")

    if args.feedback:
        # ── Feedback mode: record outcome without running analysis ─────────
        console.print(f"\n[dim]Recording feedback: {args.cve_id} → {args.feedback}[/dim]")
        asyncio.run(record_feedback(args.cve_id, args.feedback, args.notes))
        console.print(f"[green]✓ Feedback recorded.[/green] Run again without --feedback to see it used in the next analysis.")
    else:
        # ── Analysis mode: recall → analyse → remember ─────────────────────
        analysis, tool_log, history, context_budget = asyncio.run(analyse_cve(args.cve_id))

        console.print()
        display_memory_context(history)
        console.print()
        display_analysis(analysis)
        console.print()
        console.print(
            f"[dim]Context budget: {context_budget.used_tokens}/{context_budget.budget_tokens} tokens"
            f" — {context_budget.entries_verbatim} verbatim, {context_budget.entries_summarized} summarized"
            f"{' (truncated)' if context_budget.was_truncated else ''}[/dim]"
        )
        console.print(
            f"[dim]To record what happened next:[/dim]\n"
            f"  [cyan]python levels/l5_memory.py {args.cve_id} --feedback patched --notes 'Upgraded to 2.17.1'[/cyan]\n"
            f"  [cyan]python levels/l5_memory.py {args.cve_id} --feedback dismissed --notes 'Not affected — using log4j-api only'[/cyan]"
        )
