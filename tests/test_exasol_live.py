"""Live Exasol integration tests.

Skipped by default (they need a running database and loaded data):

    docker run -d --name exasol -p 8563:8563 \
        -e EXASOL_PASSWORD=... exasol/docker-db:7.1.30
    python scripts/init_exasol.py
    python scripts/load_synthetic_to_exasol.py
    pytest tests/test_exasol_live.py -m integration

Run from the repo root so `.env` is found.
"""

import os

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load_env() -> None:
    path = os.path.join(ROOT, ".env")
    if not os.path.isfile(path):
        return
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _exasol_env():
    """Load .env only when these tests actually run.

    Doing this at import time would leak EXASOL_PASSWORD into every other test
    module (pytest imports all of them during collection), making each app
    startup attempt a real database connection.
    """
    _load_env()


def _live_conn():
    """A usable connection, or skips gracefully if no live database is running.

    The loader falls back to mock rows on any query error, and mock rows are
    indistinguishable from real ones by shape, so a live test that only checks
    the return value passes on the fallback. Assert the connection first.
    """
    import exasol_loader

    conn = exasol_loader._get_connection()
    if conn is None or getattr(conn, "is_closed", False):
        pytest.skip("Exasol live database not available on localhost:8563")
    return conn


def test_exasol_connection_live():
    assert _live_conn() is not None


def test_fetch_recent_returns_real_rows():
    import exasol_loader

    conn = _live_conn()
    rows = exasol_loader.fetch_recent_transactions(10)
    assert len(rows) == 10
    assert rows[0]["txn_id"].startswith("UPI-")

    # The live table must actually hold the row we were handed: the mock
    # fallback would satisfy the checks above on its own.
    row = conn.execute(
        f"SELECT COUNT(*) AS n FROM upi_transactions "
        f"WHERE txn_id = {exasol_loader._sql_literal(rows[0]['txn_id'])}"
    ).fetchone()
    assert int(row["n"]) >= 1


def test_upi_transactions_populated():
    conn = _live_conn()
    row = conn.execute("SELECT COUNT(*) AS n FROM upi_transactions").fetchone()
    assert int(row["n"]) >= 10_000
