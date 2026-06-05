"""
tests/conftest.py — Shared pytest fixtures for Vigil integration tests.

These tests require a running PostgreSQL instance.
The easiest way is to start the Docker Compose stack first:

    docker compose up -d db

Then run tests from the project root:

    pip install -e ".[api,dev]"
    pytest tests/ -v

Set DATABASE_URL to override the default connection string:

    DATABASE_URL=postgresql://vigil:vigil@localhost:5432/vigil pytest tests/
"""

import asyncio
import os

import asyncpg
import pytest
import pytest_asyncio

# ─── Connection string ────────────────────────────────────────────────────────
# Uses the same default as the level files so tests work against the Docker DB.
TEST_DB_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://vigil:vigil@localhost:5432/vigil",
)


# ─── Event loop ───────────────────────────────────────────────────────────────
# pytest-asyncio needs a shared event loop across the test session.

@pytest.fixture(scope="session")
def event_loop():
    """Create a single event loop for the whole test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ─── Database connection ──────────────────────────────────────────────────────

@pytest_asyncio.fixture(scope="function")
async def db_conn():
    """
    Provide a fresh asyncpg connection for each test.

    The fixture yields after connecting and closes the connection afterwards.
    If the database is unreachable the test is automatically skipped — this
    means the test suite doesn't hard-fail in environments without PostgreSQL
    (e.g. CI without the Docker stack).
    """
    try:
        conn = await asyncpg.connect(TEST_DB_URL)
    except Exception as exc:
        pytest.skip(f"PostgreSQL not reachable ({exc}) — start 'docker compose up -d db' first")
        return

    yield conn
    await conn.close()


# ─── Isolated watchlist ───────────────────────────────────────────────────────

@pytest_asyncio.fixture(scope="function")
async def clean_watchlist(db_conn):
    """
    Ensure the watchlist and related tables exist and are FULLY empty
    before each test that exercises the L6 scanner.

    Why a full wipe (and not just CVE-TEST-% rows):
      Tests like test_empty_watchlist_returns_zero assert
      `summary["scanned"] == 0`. If a previous interactive run of the L6
      level added real CVEs (e.g. CVE-2024-12345) those rows survive a
      prefix-scoped cleanup and pollute the count, producing failures
      like `assert 2 == 0`.

      Since these fixtures only run against the disposable docker-compose
      `db` service (or an explicitly opted-in DATABASE_URL), wiping all
      rows is the right behaviour for test isolation.
    """
    from levels.l6_autonomous import init_db_l6

    await init_db_l6(db_conn)

    # Full wipe before the test — guarantees a clean slate regardless of
    # what previous runs (test or interactive) left behind.
    await db_conn.execute("DELETE FROM alerts")
    await db_conn.execute("DELETE FROM scan_state")
    await db_conn.execute("DELETE FROM watchlist")

    yield db_conn  # test runs here

    # Teardown: same wipe so the next test starts clean too.
    await db_conn.execute("DELETE FROM alerts")
    await db_conn.execute("DELETE FROM scan_state")
    await db_conn.execute("DELETE FROM watchlist")
