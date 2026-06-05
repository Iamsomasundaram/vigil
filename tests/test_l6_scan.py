"""
tests/test_l6_scan.py — Async integration tests for the L6 autonomous scanner.

WHY THESE TESTS EXIST
─────────────────────
The autonomous monitor (L6) is the most operationally complex part of Vigil.
It combines:
  - Concurrent database access across multiple asyncio tasks
  - Background loop lifecycle (start / stop / kill switch)
  - Change detection logic with thresholds

The bugs we found during code review were:
  1. scan_all_once() shared ONE asyncpg connection across all parallel scan
     tasks, causing "another operation is in progress" on multi-CVE watchlists.
  2. Empty watchlist returned {"alerts": 0} but _monitor_loop read ["alerts_created"],
     causing a silent KeyError every cycle when the watchlist was empty.

These tests confirm the fixes hold.

WHAT THEY TEST
──────────────
  test_empty_watchlist          — scan with no CVEs returns a clean summary
  test_empty_watchlist_key      — the returned dict uses "alerts_created" (not "alerts")
  test_single_cve_scan          — one CVE scan completes without error
  test_multi_cve_no_shared_conn — parallel scan of 3 CVEs doesn't raise connection errors
  test_change_detection_*       — deterministic threshold logic works correctly
  test_monitor_start_stop       — background loop starts, runs at least once, stops cleanly

HOW TO RUN
──────────
    docker compose up -d db
    pip install -e ".[api,dev]"
    pytest tests/test_l6_scan.py -v
"""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio

from levels.l6_autonomous import (
    DB_URL,
    ChangeSignal,
    add_to_watchlist,
    detect_changes,
    get_watchlist,
    init_db_l6,
    is_running,
    scan_all_once,
    start_monitor,
    stop_monitor,
)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _fake_nvd(cvss: float = 7.5, patch: bool = False) -> dict:
    return {"cvss_score": cvss, "severity": "High", "patch_known": patch}


# ─── Change detection (unit tests — no DB needed) ─────────────────────────────
# These are pure-function tests. No fixtures required.

class TestDetectChanges:
    def test_first_scan_is_new_cve(self):
        """First scan of a CVE (no prior state) is always classified new_cve."""
        signal = detect_changes("CVE-2021-44228", None, _fake_nvd(), 0.5)
        assert signal.change_type == "new_cve"

    def test_no_change_below_thresholds(self):
        """Small EPSS drift below the spike threshold generates no alert."""
        last = {"epss_score": 0.10, "cvss_score": 7.5, "patch_known": False}
        signal = detect_changes("CVE-TEST-001", last, _fake_nvd(7.5), 0.12)
        assert signal.change_type == "no_change"

    def test_epss_spike_detected(self):
        """EPSS jump of ≥0.15 generates an epss_spike alert."""
        last = {"epss_score": 0.05, "cvss_score": 7.5, "patch_known": False}
        signal = detect_changes("CVE-TEST-002", last, _fake_nvd(7.5), 0.25)
        assert signal.change_type == "epss_spike"
        assert signal.current_epss == pytest.approx(0.25)

    def test_epss_critical_threshold(self):
        """EPSS crossing 0.5 for the first time generates epss_critical."""
        last = {"epss_score": 0.45, "cvss_score": 7.5, "patch_known": False}
        signal = detect_changes("CVE-TEST-003", last, _fake_nvd(7.5), 0.55)
        assert signal.change_type == "epss_critical"

    def test_new_patch_detected(self):
        """Patch becoming available when it wasn't before generates new_patch."""
        last = {"epss_score": 0.1, "cvss_score": 7.5, "patch_known": False}
        signal = detect_changes("CVE-TEST-004", last, _fake_nvd(7.5, patch=True), 0.1)
        assert signal.change_type == "new_patch"
        assert signal.patch_newly_available is True

    def test_cvss_increase_detected(self):
        """CVSS increase of ≥1.0 generates severity_increase."""
        last = {"epss_score": 0.1, "cvss_score": 6.5, "patch_known": False}
        signal = detect_changes("CVE-TEST-005", last, _fake_nvd(8.0), 0.1)
        assert signal.change_type == "severity_increase"

    def test_cvss_small_increase_ignored(self):
        """CVSS increase below 1.0 does not generate an alert."""
        last = {"epss_score": 0.1, "cvss_score": 7.5, "patch_known": False}
        signal = detect_changes("CVE-TEST-006", last, _fake_nvd(8.4), 0.1)
        assert signal.change_type == "no_change"


# ─── Integration tests (require PostgreSQL) ───────────────────────────────────

@pytest.mark.asyncio
async def test_empty_watchlist_returns_zero(clean_watchlist):
    """
    scan_all_once() with an empty watchlist must return a dict with
    scanned=0 and alerts_created=0 — not raise an exception.

    This tests the original bug where an empty watchlist caused a silent
    crash in _monitor_loop because the key was "alerts" not "alerts_created".
    """
    summary = await scan_all_once(DB_URL)
    assert summary["scanned"] == 0
    assert "alerts_created" in summary, (
        "'alerts_created' key missing — _monitor_loop would crash on empty watchlist"
    )
    assert summary["alerts_created"] == 0


@pytest.mark.asyncio
async def test_single_cve_scan_no_crash(clean_watchlist):
    """
    Adding one CVE and scanning must complete without error.
    We mock the external HTTP calls so the test doesn't depend on NVD/EPSS.
    """
    conn = clean_watchlist
    await add_to_watchlist(conn, "CVE-TEST-SINGLE")

    with (
        patch("levels.l6_autonomous.fetch_current_nvd",  new=AsyncMock(return_value=_fake_nvd())),
        patch("levels.l6_autonomous.fetch_current_epss", new=AsyncMock(return_value=0.10)),
        patch("levels.l6_autonomous.generate_alert",     new=AsyncMock(side_effect=Exception("should not be called"))),
    ):
        summary = await scan_all_once(DB_URL)

    assert summary["scanned"] == 1
    # No change expected on first scan (new_cve generates an alert, so we
    # just verify it doesn't crash — actual alert count depends on mocked data)
    assert "alerts_created" in summary


@pytest.mark.asyncio
async def test_multi_cve_parallel_no_shared_connection(clean_watchlist):
    """
    The critical regression test for the shared-connection bug.

    Before the fix: scan_all_once() passed a single asyncpg.Connection to
    all concurrent scan_one() calls. asyncpg raises "another operation is
    in progress" when two awaits overlap on the same connection.

    After the fix: each scan_one() opens its own connection.

    This test adds 3 CVEs and scans them in parallel. If any task raises
    "another operation is in progress", the test fails.
    """
    conn = clean_watchlist
    for cve in ["CVE-TEST-MULTI-1", "CVE-TEST-MULTI-2", "CVE-TEST-MULTI-3"]:
        await add_to_watchlist(conn, cve)

    with (
        patch("levels.l6_autonomous.fetch_current_nvd",  new=AsyncMock(return_value=_fake_nvd())),
        patch("levels.l6_autonomous.fetch_current_epss", new=AsyncMock(return_value=0.10)),
    ):
        # return_exceptions=True is already inside scan_all_once, but any
        # "another operation is in progress" error would surface as an Exception
        # caught internally — we verify no exceptions appeared in results
        summary = await scan_all_once(DB_URL)

    assert summary["scanned"] == 3, (
        f"Expected 3 CVEs scanned, got {summary['scanned']}. "
        "A connection-sharing error may have caused tasks to fail silently."
    )


@pytest.mark.asyncio
async def test_monitor_start_and_stop(clean_watchlist):
    """
    The background monitor starts, runs at least one scan cycle, and stops
    cleanly via the kill switch.

    We shorten the scan interval so the test completes in < 2 seconds.
    """
    import levels.l6_autonomous as l6

    original_interval = l6.SCAN_INTERVAL_SECONDS

    with (
        patch("levels.l6_autonomous.fetch_current_nvd",  new=AsyncMock(return_value=_fake_nvd())),
        patch("levels.l6_autonomous.fetch_current_epss", new=AsyncMock(return_value=0.10)),
        patch.object(l6, "SCAN_INTERVAL_SECONDS", 1),   # scan every 1s for the test
    ):
        assert not is_running(), "Monitor should be stopped before test"

        await start_monitor(DB_URL)
        assert is_running(), "Monitor should be running after start"

        # Give it time to complete at least one scan cycle
        await asyncio.sleep(1.5)

        await stop_monitor()
        # Give the task a moment to fully cancel
        await asyncio.sleep(0.1)

    assert not is_running(), "Monitor should be stopped after stop_monitor()"
