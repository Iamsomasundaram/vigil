"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  VIGIL — Level 6: Fully Autonomous Monitoring                              ║
║                                                                              ║
║  The agent runs continuously without human prompting.                        ║
║  It watches a CVE list, detects changes, and fires alerts on its own.       ║
╚══════════════════════════════════════════════════════════════════════════════╝

CONCEPTS COVERED
────────────────
  1. Autonomous operation     — agent acts on goals without being asked each time
  2. Background task loop     — asyncio.Task running perpetually alongside the API
  3. Change detection         — comparing current state against memory to find signals
  4. Self-directed alerting   — agent decides when something matters, not humans
  5. Kill switch              — immediate stop of all autonomous activity (safety)
  6. Composition              — L6 is built from every prior level working together

WHAT MAKES AN AGENT "AUTONOMOUS"?
───────────────────────────────────
  There is an important distinction:

  AUTOMATED (L1–L5):
    Human asks → agent runs → human reads result → repeat
    The agent is reactive. Nothing happens without a trigger from you.

  AUTONOMOUS (L6):
    Agent has its own goals and acts on them continuously.
    You ADD a CVE to the watchlist. The agent:
      - Checks it on a schedule (without you asking)
      - Detects when something changed
      - Decides whether the change is significant
      - Generates and stores an alert
      - You check alerts when you want — they're already there

    The agent is proactive. It works while you sleep.

  The line between "automated" and "autonomous" is:
    Does the agent INITIATE action, or just RESPOND to it?

HOW L6 COMPOSES EVERY PRIOR LEVEL
────────────────────────────────────
  L6 doesn't replace earlier levels — it orchestrates them:

    L2 (parallel fan-out)   → scan multiple CVEs simultaneously each loop tick
    L3 (routing)            → decide alert severity: is this Critical or just Monitor?
    L4 (tool use)           → fetch live NVD + EPSS data on each scan cycle
    L5 (memory)             → compare current data against last known state to detect change

  This is the pattern at the heart of all production agentic systems:
  start simple (L0), add structure (L1–L3), add tools (L4), add memory (L5),
  then close the loop into continuous autonomous operation (L6).

THE MONITOR LOOP PATTERN
─────────────────────────
  The core of L6 is a background asyncio.Task that runs forever:

    while not stop_requested:
        watchlist = read watchlist from DB
        scan all CVEs in parallel  (L2 fan-out)
        for each CVE:
            fetch current data      (L4 tools)
            compare against memory  (L5)
            if significant change:
                route alert severity (L3)
                store alert in DB
        sleep until next scan interval

  The loop is interruptible. When the kill switch fires, the sleep is
  cancelled immediately — the agent doesn't finish its current nap,
  it stops right now.

CHANGE DETECTION: WHAT IS "SIGNIFICANT"?
─────────────────────────────────────────
  Not every data change deserves an alert. Change detection filters noise:

  SIGNAL (generates alert):
    • EPSS score jumped by ≥ 0.15   (e.g., 0.10 → 0.25 — threat is escalating)
    • EPSS crossed the 0.5 threshold (now more likely than not to be exploited)
    • New patch became available     (you can act now when you couldn't before)
    • CVSS score increased           (vendor re-assessed and it's worse)

  NOISE (no alert):
    • EPSS changed by < 0.05        (normal daily fluctuation)
    • No data changed at all        (routine confirm, just update last-checked)
    • CVE already has "patched" feedback (we fixed it — don't keep alerting)

  This threshold logic is why the agent is useful: it does the triage for you.
  A human checking 500 CVEs manually every morning would miss the subtle ones.
  The agent catches EPSS creep — a CVE that was safe last week is now dangerous.

HUMAN OVERSIGHT: THE KILL SWITCH
──────────────────────────────────
  Autonomy without oversight is dangerous. L6 implements two safety controls:

  1. KILL SWITCH — `POST /l6/monitor/stop`
     Immediately cancels the background task. The agent stops all activity
     within seconds. This is not graceful shutdown — it's an emergency brake.
     Idempotent: calling it multiple times is safe.

  2. ALERT ACKNOWLEDGEMENT — `POST /l6/alerts/{id}/acknowledge`
     Humans review and acknowledge alerts. Unacknowledged alerts stay visible.
     This creates an audit trail: every alert was either acted on or consciously
     dismissed by a human. The agent never assumes its alerts were seen.

  In production: add webhook notifications, Slack/PagerDuty integration,
  auto-escalation if alerts go unacknowledged for N hours. The DB schema
  here supports all of these as extensions.

THE ESCALATION LADDER
──────────────────────
  When a change is detected, the agent applies a 3-tier ladder:

    Tier 1: INFORMATIONAL — EPSS moved, but still low risk. Log it, no noise.
    Tier 2: WARNING       — EPSS spike or new patch. Store alert, needs attention.
    Tier 3: CRITICAL      — EPSS > 0.5 or active exploitation. Alert + flag urgent.

  The agent generates the alert but never acts autonomously beyond alerting.
  It does not patch systems, does not open tickets, does not send emails.
  It informs. Humans decide.

  This is the correct posture for agentic security tooling today:
  full autonomy in DETECTION, human authority in RESPONSE.

RUN THIS FILE
─────────────
  # Add CVEs to the watchlist and run one manual scan:
  python levels/l6_autonomous.py --add CVE-2021-44228
  python levels/l6_autonomous.py --add CVE-2023-44487
  python levels/l6_autonomous.py --scan

  # List the watchlist and any alerts:
  python levels/l6_autonomous.py --status

  # The autonomous loop is started via the API (it runs inside FastAPI):
  #   POST /l6/monitor/start
  #   GET  /l6/monitor/status
  #   POST /l6/monitor/stop   (kill switch)
"""

import argparse
import asyncio
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

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

load_dotenv(Path(__file__).parent.parent / ".env")

console = Console()
client  = AsyncOpenAI(timeout=60.0)
MODEL   = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
DB_URL  = os.getenv("DATABASE_URL", "postgresql://vigil:vigil@localhost:5432/vigil")

# Scan interval: how often the autonomous loop checks each CVE.
# 3600 = 1 hour in production. 60 = 1 minute for demo/testing.
SCAN_INTERVAL_SECONDS = int(os.getenv("VIGIL_SCAN_INTERVAL", "3600"))

# Thresholds that determine when a change is "significant" enough to alert
EPSS_SPIKE_THRESHOLD     = 0.15   # alert if EPSS increases by this much
EPSS_CRITICAL_THRESHOLD  = 0.50   # always alert if EPSS crosses this line

http = httpx.AsyncClient(timeout=15.0)


# ─── SCHEMA HELPERS ───────────────────────────────────────────────────────────

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

class AlertSeverity(str):
    CRITICAL     = "Critical"
    WARNING      = "Warning"
    INFORMATIONAL = "Informational"


class ChangeSignal(_Base):
    """
    What the change detector found when comparing current data against memory.

    This is an internal model — it's never returned to API callers directly.
    It carries the raw signal from which the alert is built.
    """
    cve_id:        str
    change_type:   Literal[
        "epss_spike",           # EPSS rose significantly
        "epss_critical",        # EPSS crossed the 0.5 exploitation threshold
        "new_patch",            # patch became available that wasn't before
        "severity_increase",    # CVSS score went up (vendor re-assessment)
        "new_cve",              # first time we've seen data for this CVE
        "no_change",            # routine scan, nothing significant happened
    ]
    previous_epss: float
    current_epss:  float
    previous_cvss: float
    current_cvss:  float
    patch_newly_available: bool
    summary:       str   = Field(description="One sentence: what changed")


class AutonomousAlert(_Base):
    """
    A generated alert — the primary output of the autonomous monitoring loop.

    Stored in PostgreSQL and surfaced via the API. Humans review and
    acknowledge these alerts to close the loop.
    """
    cve_id:             str
    alert_type:         str   = Field(description="Which change triggered this alert")
    severity:           Literal["Critical", "Warning", "Informational"]
    summary:            str   = Field(description="Plain-English description of what changed")
    recommended_action: str   = Field(description="What the team should do about this")
    epss_now:           float = Field(ge=0.0, le=1.0)
    cvss_now:           float
    auto_generated:     bool  = Field(default=True)


# ─── DATABASE LAYER ───────────────────────────────────────────────────────────
# L6 adds three new tables on top of the L5 schema.
# All tables are created idempotently so L5 and L6 can coexist.

async def init_db_l6(conn: asyncpg.Connection) -> None:
    """
    Create L6-specific tables.

    watchlist  — CVEs the agent actively monitors
    alerts     — generated by the autonomous loop, read by humans
    scan_state — last known data per CVE, used for change detection
    """
    # The watchlist: which CVEs to monitor and when we last checked them
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS watchlist (
            id           SERIAL PRIMARY KEY,
            cve_id       TEXT        NOT NULL UNIQUE,
            added_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            last_scanned TIMESTAMPTZ,
            active       BOOLEAN     NOT NULL DEFAULT TRUE
        )
    """)

    # Alerts generated by the autonomous loop
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS alerts (
            id              SERIAL PRIMARY KEY,
            cve_id          TEXT        NOT NULL,
            alert_type      TEXT        NOT NULL,
            severity        TEXT        NOT NULL,
            summary         TEXT        NOT NULL,
            recommended_action TEXT     NOT NULL,
            epss_now        FLOAT,
            cvss_now        FLOAT,
            acknowledged    BOOLEAN     NOT NULL DEFAULT FALSE,
            acknowledged_at TIMESTAMPTZ,
            acknowledged_by TEXT,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    # Last-known state per CVE — the baseline the change detector compares against.
    # Without this, every scan would have no "before" to compare against.
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS scan_state (
            cve_id       TEXT    PRIMARY KEY,
            epss_score   FLOAT   NOT NULL DEFAULT 0.0,
            cvss_score   FLOAT   NOT NULL DEFAULT 0.0,
            patch_known  BOOLEAN NOT NULL DEFAULT FALSE,
            last_updated TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    await conn.execute("CREATE INDEX IF NOT EXISTS idx_alerts_cve_id ON alerts(cve_id)")
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_alerts_acknowledged ON alerts(acknowledged)")


async def add_to_watchlist(conn: asyncpg.Connection, cve_id: str) -> bool:
    """
    Add a CVE to the watchlist. Returns True if newly added, False if already present.

    Uses ON CONFLICT DO UPDATE to reactivate a previously removed CVE
    without creating a duplicate row.
    """
    result = await conn.fetchval(
        """
        INSERT INTO watchlist (cve_id)
        VALUES ($1)
        ON CONFLICT (cve_id) DO UPDATE
            SET active = TRUE
        RETURNING (xmax = 0)  -- xmax=0 means it was an INSERT not an UPDATE
        """,
        cve_id,
    )
    return bool(result)


async def remove_from_watchlist(conn: asyncpg.Connection, cve_id: str) -> None:
    """Deactivate a CVE from monitoring (soft delete — keeps history)."""
    await conn.execute(
        "UPDATE watchlist SET active = FALSE WHERE cve_id = $1", cve_id
    )


async def get_watchlist(conn: asyncpg.Connection) -> list[dict]:
    """Return all active CVEs being monitored."""
    rows = await conn.fetch(
        "SELECT cve_id, added_at, last_scanned FROM watchlist WHERE active = TRUE ORDER BY added_at"
    )
    return [dict(r) for r in rows]


async def get_scan_state(conn: asyncpg.Connection, cve_id: str) -> dict | None:
    """Return the last known data snapshot for a CVE, or None if never scanned."""
    row = await conn.fetchrow("SELECT * FROM scan_state WHERE cve_id = $1", cve_id)
    return dict(row) if row else None


async def save_scan_state(
    conn: asyncpg.Connection,
    cve_id: str,
    epss: float,
    cvss: float,
    patch_known: bool,
) -> None:
    """
    Update the last-known state for a CVE.

    This is the "memory" the change detector uses. Called after every scan
    so the next scan has a baseline to compare against.
    """
    await conn.execute(
        """
        INSERT INTO scan_state (cve_id, epss_score, cvss_score, patch_known)
        VALUES ($1, $2, $3, $4)
        ON CONFLICT (cve_id) DO UPDATE
            SET epss_score   = EXCLUDED.epss_score,
                cvss_score   = EXCLUDED.cvss_score,
                patch_known  = EXCLUDED.patch_known,
                last_updated = NOW()
        """,
        cve_id, epss, cvss, patch_known,
    )


async def save_alert(conn: asyncpg.Connection, alert: AutonomousAlert) -> int:
    """Persist a generated alert. Returns the new alert ID."""
    return await conn.fetchval(
        """
        INSERT INTO alerts (cve_id, alert_type, severity, summary, recommended_action, epss_now, cvss_now)
        VALUES ($1, $2, $3, $4, $5, $6, $7)
        RETURNING id
        """,
        alert.cve_id, alert.alert_type, alert.severity,
        alert.summary, alert.recommended_action,
        alert.epss_now, alert.cvss_now,
    )


async def get_alerts(
    conn: asyncpg.Connection,
    unacknowledged_only: bool = False,
    limit: int = 50,
) -> list[dict]:
    """Retrieve alerts, newest first. Optionally filter to unacknowledged only."""
    where = "WHERE NOT acknowledged" if unacknowledged_only else ""
    rows  = await conn.fetch(
        f"SELECT * FROM alerts {where} ORDER BY created_at DESC LIMIT $1", limit
    )
    return [dict(r) for r in rows]


async def acknowledge_alert(conn: asyncpg.Connection, alert_id: int, by: str = "api") -> bool:
    """Mark an alert as acknowledged. Returns True if the alert existed."""
    result = await conn.execute(
        """
        UPDATE alerts
        SET acknowledged = TRUE, acknowledged_at = NOW(), acknowledged_by = $2
        WHERE id = $1 AND NOT acknowledged
        """,
        alert_id, by,
    )
    return result != "UPDATE 0"


async def mark_last_scanned(conn: asyncpg.Connection, cve_id: str) -> None:
    """Update the last_scanned timestamp for a watchlist entry."""
    await conn.execute(
        "UPDATE watchlist SET last_scanned = NOW() WHERE cve_id = $1", cve_id
    )


# ─── LIVE DATA FETCHERS ───────────────────────────────────────────────────────
# Same NVD + EPSS calls as L4/L5, but as plain async functions (no tool-calling
# loop here — the autonomous scanner is not having a "conversation", it just
# needs the raw numbers to compare against baseline).

async def fetch_current_nvd(cve_id: str) -> dict:
    """Fetch current NVD data. Returns a dict with cvss_score, severity, patch_known."""
    url = f"https://services.nvd.nist.gov/rest/json/cves/2.0?cveId={cve_id}"
    try:
        r = await http.get(url)
        r.raise_for_status()
        vulns = r.json().get("vulnerabilities", [])
        if not vulns:
            return {"cvss_score": 0.0, "severity": "Unknown", "patch_known": False}

        cve     = vulns[0]["cve"]
        metrics = cve.get("metrics", {})
        score   = 0.0
        for key in ("cvssMetricV31", "cvssMetricV30", "cvssMetricV2"):
            if key in metrics:
                score = metrics[key][0]["cvssData"].get("baseScore", 0.0)
                break

        # Heuristic for patch availability: check if references include
        # common patch-signal patterns in their URL or tags
        refs     = cve.get("references", [])
        ref_tags = [tag for r in refs for tag in r.get("tags", [])]
        patch_known = any(
            t in ("Patch", "Vendor Advisory", "Mitigation") for t in ref_tags
        )

        return {"cvss_score": float(score or 0), "severity": "Unknown", "patch_known": patch_known}
    except Exception:
        return {"cvss_score": 0.0, "severity": "Unknown", "patch_known": False}


async def fetch_current_epss(cve_id: str) -> float:
    """Fetch current EPSS score. Returns 0.0 on any failure."""
    url = f"https://api.first.org/data/v1/epss?cve={cve_id}"
    try:
        r = await http.get(url)
        r.raise_for_status()
        items = r.json().get("data", [])
        return float(items[0].get("epss", 0)) if items else 0.0
    except Exception:
        return 0.0


# ─── CHANGE DETECTION ─────────────────────────────────────────────────────────

def detect_changes(
    cve_id:      str,
    last_state:  dict | None,
    current_nvd: dict,
    current_epss: float,
) -> ChangeSignal:
    """
    Compare current data against the last known state and classify the change.

    This is a deterministic function — no LLM involved. The thresholds are
    explicit rules. The LLM is called AFTER this to generate human-readable
    alert text, but the decision of WHAT changed is made here, in code.

    Why deterministic change detection instead of asking the LLM?
      Reliability. An LLM might interpret "0.01 → 0.02" as significant
      on one run and insignificant on another. Code is consistent.
      The LLM's job is to communicate the finding well, not to make it.
    """
    prev_epss = last_state["epss_score"] if last_state else 0.0
    prev_cvss = last_state["cvss_score"] if last_state else 0.0
    prev_patch = last_state["patch_known"] if last_state else False

    curr_epss  = current_epss
    curr_cvss  = current_nvd["cvss_score"]
    curr_patch = current_nvd["patch_known"]

    epss_delta = curr_epss - prev_epss

    # Priority order: most severe change wins
    if last_state is None:
        change_type = "new_cve"
        summary = f"First scan of {cve_id}: EPSS={curr_epss:.3f}, CVSS={curr_cvss}"
    elif curr_epss >= EPSS_CRITICAL_THRESHOLD and prev_epss < EPSS_CRITICAL_THRESHOLD:
        change_type = "epss_critical"
        summary = f"EPSS crossed critical threshold: {prev_epss:.3f} → {curr_epss:.3f} (>{EPSS_CRITICAL_THRESHOLD})"
    elif epss_delta >= EPSS_SPIKE_THRESHOLD:
        change_type = "epss_spike"
        summary = f"EPSS spiked by {epss_delta:.3f}: {prev_epss:.3f} → {curr_epss:.3f}"
    elif curr_patch and not prev_patch:
        change_type = "new_patch"
        summary = f"Patch became available (EPSS={curr_epss:.3f}, CVSS={curr_cvss})"
    elif curr_cvss > prev_cvss and (curr_cvss - prev_cvss) >= 1.0:
        change_type = "severity_increase"
        summary = f"CVSS score increased: {prev_cvss} → {curr_cvss}"
    else:
        change_type = "no_change"
        summary = f"No significant change (EPSS={curr_epss:.3f}, CVSS={curr_cvss})"

    return ChangeSignal(
        cve_id=cve_id,
        change_type=change_type,
        previous_epss=prev_epss,
        current_epss=curr_epss,
        previous_cvss=prev_cvss,
        current_cvss=curr_cvss,
        patch_newly_available=(curr_patch and not prev_patch),
        summary=summary,
    )


# ─── ALERT GENERATION ─────────────────────────────────────────────────────────

async def generate_alert(signal: ChangeSignal) -> AutonomousAlert:
    """
    Given a detected change, ask the LLM to generate a clear, actionable alert.

    The WHAT (change_type, deltas) is already determined by detect_changes().
    The LLM's job here is the HOW: phrase the alert clearly and recommend
    the right action. This is a single, focused LLM call — not a multi-step chain.

    Severity mapping:
      epss_critical, new_cve (high EPSS)  → Critical
      epss_spike, severity_increase       → Warning
      new_patch, everything else          → Informational
    """
    severity_map = {
        "epss_critical":   "Critical",
        "epss_spike":      "Warning",
        "severity_increase": "Warning",
        "new_patch":       "Informational",
        "new_cve":         "Warning" if signal.current_epss > 0.3 else "Informational",
        "no_change":       "Informational",
    }
    severity = severity_map.get(signal.change_type, "Warning")

    response = await client.chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are an autonomous security monitoring agent. "
                    "A change has been detected in a tracked CVE. "
                    "Write a clear, concise alert and a specific recommended action. "
                    "Be direct — this alert goes to security engineers who need to act fast."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"CVE: {signal.cve_id}\n"
                    f"Change detected: {signal.summary}\n"
                    f"Previous EPSS: {signal.previous_epss:.4f} | Current EPSS: {signal.current_epss:.4f}\n"
                    f"Previous CVSS: {signal.previous_cvss} | Current CVSS: {signal.current_cvss}\n"
                    f"Patch newly available: {signal.patch_newly_available}\n"
                    f"Alert severity: {severity}\n\n"
                    "Generate the alert summary and recommended action."
                ),
            },
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name":   "AutonomousAlert",
                "strict": True,
                "schema": _strict_schema(AutonomousAlert),
            },
        },
        temperature=0.1,
        max_tokens=512,
    )

    alert = AutonomousAlert.model_validate(
        json.loads(response.choices[0].message.content)
    )
    # Ensure the structured fields match what we detected — LLM fills in text,
    # we control the severity, scores, and type deterministically
    return AutonomousAlert(
        cve_id=signal.cve_id,
        alert_type=signal.change_type,
        severity=severity,
        summary=alert.summary,
        recommended_action=alert.recommended_action,
        epss_now=signal.current_epss,
        cvss_now=signal.current_cvss,
        auto_generated=True,
    )


# ─── SINGLE CVE SCAN ──────────────────────────────────────────────────────────

async def scan_one(cve_id: str, db_url: str = DB_URL) -> AutonomousAlert | None:
    """
    Run a complete scan cycle for one CVE:
      1. Fetch current NVD + EPSS data in parallel (L2 pattern)
      2. Load last known state from scan_state table
      3. Detect whether anything significant changed
      4. If yes: generate an alert and save it
      5. Always: update scan_state and last_scanned timestamp

    Returns the generated Alert if one was created, None otherwise.

    CONCURRENCY NOTE: Each call opens and closes its OWN database connection.
    asyncpg connections are not safe for concurrent operations on the same
    connection object — overlapping awaits raise "another operation is in
    progress". Because scan_all_once() calls this function for every CVE in
    parallel via asyncio.gather(), each task must own its connection exclusively.
    Using separate connections (or a pool) is the standard fix.
    """
    # Open a private connection for this task — safe for concurrent callers
    conn = await asyncpg.connect(db_url)
    try:
        # Fetch NVD and EPSS simultaneously — L2's parallel pattern applied here.
        # Note: these are pure HTTP calls, not DB operations, so they don't touch
        # our connection and are safe to run in parallel.
        nvd_data, epss_score = await asyncio.gather(
            fetch_current_nvd(cve_id),
            fetch_current_epss(cve_id),
        )

        last_state = await get_scan_state(conn, cve_id)
        signal     = detect_changes(cve_id, last_state, nvd_data, epss_score)

        # Save the current state as the new baseline, regardless of whether we alert
        await save_scan_state(conn, cve_id, epss_score, nvd_data["cvss_score"], nvd_data["patch_known"])
        await mark_last_scanned(conn, cve_id)

        if signal.change_type == "no_change":
            return None  # Nothing to alert on

        # Significant change: ask the LLM to phrase the alert clearly
        alert    = await generate_alert(signal)
        alert_id = await save_alert(conn, alert)
        console.print(
            f"  [bold {'red' if alert.severity == 'Critical' else 'yellow'}]"
            f"  ALERT #{alert_id} [{alert.severity}] {cve_id}: {signal.change_type}[/bold {'red' if alert.severity == 'Critical' else 'yellow'}]"
        )
        return alert
    finally:
        await conn.close()


# ─── THE AUTONOMOUS MONITOR LOOP ──────────────────────────────────────────────
# This is the heart of L6: a background asyncio.Task that runs perpetually.
#
# Module-level state so the FastAPI app can start/stop/check the loop.
# In production, use a proper distributed scheduler (Celery, APScheduler,
# cloud cron). For this learning project, asyncio.Task is sufficient and
# transparent about how it works.

_monitor_task: asyncio.Task | None = None
_stop_event   = asyncio.Event()       # Set this to stop the loop cleanly


def is_running() -> bool:
    """True if the autonomous monitor is currently active."""
    return _monitor_task is not None and not _monitor_task.done()


async def scan_all_once(db_url: str = DB_URL) -> dict:
    """
    Run one complete pass over the entire watchlist.
    Scans all CVEs in parallel (up to a concurrency cap to avoid rate limits).

    Returns a summary dict: how many CVEs scanned, how many alerts generated.
    This function can be called standalone (e.g. from the CLI) without the
    background loop running.
    """
    conn = await asyncpg.connect(db_url)
    try:
        await init_db_l6(conn)
        watchlist = await get_watchlist(conn)

        if not watchlist:
            # Use "alerts_created" (not "alerts") to match what _monitor_loop reads.
            return {"scanned": 0, "alerts_created": 0, "message": "Watchlist is empty"}

        console.print(f"[dim]  Scanning {len(watchlist)} CVE(s)...[/dim]")

        # Scan all CVEs simultaneously. We cap concurrency at 5 to avoid
        # hammering the NVD API (which rate-limits at 5 req/30s without a key).
        #
        # IMPORTANT: scan_one() opens its own connection per task. We do NOT
        # pass the parent `conn` here — that would share one connection across
        # multiple concurrent DB operations, triggering asyncpg's
        # "another operation is in progress" error.
        sem     = asyncio.Semaphore(5)
        alerts_generated = 0

        async def _scan_with_sem(entry):
            async with sem:
                return await scan_one(entry["cve_id"], db_url)

        results = await asyncio.gather(
            *[_scan_with_sem(entry) for entry in watchlist],
            return_exceptions=True,  # Don't let one failure stop the whole scan
        )

        for r in results:
            if isinstance(r, Exception):
                console.print(f"[dim red]  scan error: {r}[/dim red]")
            elif r is not None:
                alerts_generated += 1

        return {
            "scanned":        len(watchlist),
            "alerts_created": alerts_generated,
            "timestamp":      datetime.now(timezone.utc).isoformat(),
        }
    finally:
        await conn.close()


async def _monitor_loop(db_url: str) -> None:
    """
    The perpetual background loop.

    Each iteration: scan everything → sleep → repeat.
    The sleep uses _stop_event.wait(timeout=...) so the kill switch takes
    effect immediately rather than waiting out the current sleep interval.

    This function is meant to run as an asyncio.Task — call start_monitor()
    to create it, stop_monitor() to cancel it.
    """
    console.print(f"[green]  Autonomous monitor started. Scan interval: {SCAN_INTERVAL_SECONDS}s[/green]")

    while not _stop_event.is_set():
        scan_start = time.perf_counter()
        try:
            summary = await scan_all_once(db_url)
            elapsed = time.perf_counter() - scan_start
            console.print(
                f"[dim]  Scan complete: {summary['scanned']} CVEs, "
                f"{summary['alerts_created']} alerts, {elapsed:.1f}s[/dim]"
            )
        except Exception as e:
            console.print(f"[red]  Monitor loop error: {e}[/red]")

        # Sleep until next interval — but wake up instantly if stop is requested.
        # asyncio.wait_for raises TimeoutError after SCAN_INTERVAL_SECONDS,
        # which we catch as "time to scan again". If stop fires, the wait returns
        # early and the while condition fails.
        try:
            await asyncio.wait_for(_stop_event.wait(), timeout=SCAN_INTERVAL_SECONDS)
        except asyncio.TimeoutError:
            pass  # Expected — means the interval elapsed normally

    console.print("[yellow]  Autonomous monitor stopped.[/yellow]")


async def start_monitor(db_url: str = DB_URL) -> bool:
    """
    Start the autonomous monitoring background task.

    Returns True if started, False if already running.
    Idempotent: safe to call multiple times.
    """
    global _monitor_task

    if is_running():
        return False

    _stop_event.clear()
    _monitor_task = asyncio.create_task(_monitor_loop(db_url))
    return True


async def stop_monitor() -> bool:
    """
    Kill switch: immediately stop all autonomous monitoring activity.

    Sets the stop event (causes the loop to exit on its next check),
    then cancels the task (wakes it from any current sleep immediately).
    Returns True if a running task was stopped, False if nothing was running.
    """
    global _monitor_task

    if not is_running():
        return False

    _stop_event.set()
    _monitor_task.cancel()
    try:
        await _monitor_task
    except asyncio.CancelledError:
        pass  # Expected — we cancelled it

    _monitor_task = None
    return True


# ─── DISPLAY HELPERS ──────────────────────────────────────────────────────────

SEVERITY_COLOURS = {
    "Critical":      "bold red",
    "Warning":       "yellow",
    "Informational": "cyan",
}


def display_watchlist(watchlist: list[dict]) -> None:
    if not watchlist:
        console.print(Panel("[dim]Watchlist is empty. Add CVEs with --add CVE-XXXX-XXXXX[/dim]",
                            title="[bold]Watchlist[/bold]", border_style="dim"))
        return

    t = Table(box=box.SIMPLE, show_header=True, padding=(0, 1))
    t.add_column("CVE ID",       style="bold")
    t.add_column("Added",        style="dim")
    t.add_column("Last Scanned", style="dim")

    for entry in watchlist:
        added   = entry["added_at"].strftime("%Y-%m-%d") if entry.get("added_at") else "?"
        scanned = entry["last_scanned"].strftime("%Y-%m-%d %H:%M") if entry.get("last_scanned") else "Never"
        t.add_row(entry["cve_id"], added, scanned)

    console.print(Panel(t, title=f"[bold]Watchlist ({len(watchlist)} CVEs)[/bold]", border_style="cyan"))


def display_alerts(alerts: list[dict]) -> None:
    if not alerts:
        console.print(Panel("[dim]No alerts.[/dim]", title="[bold]Alerts[/bold]", border_style="dim"))
        return

    for alert in alerts[:10]:  # Show most recent 10
        severity = alert.get("severity", "Informational")
        colour   = SEVERITY_COLOURS.get(severity, "white")
        ack      = "[dim](acknowledged)[/dim]" if alert.get("acknowledged") else "[bold]NEEDS REVIEW[/bold]"
        ts       = alert["created_at"].strftime("%Y-%m-%d %H:%M") if alert.get("created_at") else "?"

        console.print(Panel(
            f"[{colour}]{alert.get('summary', '')}[/{colour}]\n\n"
            f"[bold]Action:[/bold] {alert.get('recommended_action', '')}\n"
            f"EPSS: {alert.get('epss_now', 0):.4f}  CVSS: {alert.get('cvss_now', 0)}  {ack}",
            title=f"[bold]Alert #{alert['id']} [{severity}] — {alert['cve_id']}[/bold]  [dim]{ts}[/dim]",
            border_style=colour.replace("bold ", ""),
        ))


# ─── ENTRY POINT ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="VIGIL L6 — Autonomous CVE Monitor")
    parser.add_argument("--add",    metavar="CVE_ID", help="Add a CVE to the watchlist")
    parser.add_argument("--remove", metavar="CVE_ID", help="Remove a CVE from the watchlist")
    parser.add_argument("--scan",   action="store_true", help="Run one manual scan of the watchlist")
    parser.add_argument("--status", action="store_true", help="Show watchlist and recent alerts")
    args = parser.parse_args()

    console.print()
    console.print(Text("VIGIL", style="bold cyan") + Text(" — Level 6: Autonomous Monitoring", style="dim"))
    console.print(f"[dim]Scan interval: {SCAN_INTERVAL_SECONDS}s  |  DB: {DB_URL}[/dim]")

    async def _run():
        conn = await asyncpg.connect(DB_URL)
        try:
            await init_db_l6(conn)

            if args.add:
                newly_added = await add_to_watchlist(conn, args.add)
                status = "added" if newly_added else "reactivated (was already present)"
                console.print(f"[green]✓ {args.add} {status}[/green]")

            elif args.remove:
                await remove_from_watchlist(conn, args.remove)
                console.print(f"[yellow]✓ {args.remove} removed from watchlist[/yellow]")

            elif args.scan:
                console.print(f"\n[dim]Running manual scan...[/dim]")
                summary = await scan_all_once()
                console.print(f"\n[green]Scan complete: {summary['scanned']} CVEs scanned, {summary['alerts_created']} alerts generated[/green]")

            elif args.status:
                watchlist = await get_watchlist(conn)
                alerts    = await get_alerts(conn, limit=10)
                console.print()
                display_watchlist(watchlist)
                console.print()
                display_alerts(alerts)

            else:
                parser.print_help()
        finally:
            await conn.close()

    asyncio.run(_run())
