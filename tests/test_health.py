"""Contract tests for GET /health and GET /version.

These are fast (TestClient, no live server) and belong in the default suite.
The original /health contract (status, model_version) is asserted in
test_backend.py; here we cover the additive hardening fields.
"""

import re

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """TestClient with caches cleared so the real artifact loads (not mock)."""
    import inference

    inference._MODEL_CACHE.clear()
    inference._EMBEDDING_STORE = None
    from backend import app

    with TestClient(app) as c:
        yield c


def test_health_includes_contract(client):
    body = client.get("/health").json()

    assert body["status"] == "ok"
    assert body["model_contract"] in {"upi", "paysim"}
    # The UPI artifact is present in this checkout, and load_model prefers it.
    assert body["model_contract"] == "upi"


def test_health_includes_embeddings_count(client):
    body = client.get("/health").json()

    assert isinstance(body["embeddings_loaded"], int)
    assert body["embeddings_loaded"] > 0
    assert isinstance(body["calibrated"], bool)
    assert "commit" in body


def test_health_reports_measured_p99(client):
    """p99 comes from the load-test artifact, not from a hard-coded claim."""
    import json
    from pathlib import Path

    body = client.get("/health").json()

    assert "p99_ms" in body and "p99_worst_ms" in body
    artifact = Path("artifacts/load_test.json")
    if not artifact.exists():
        assert body["p99_ms"] is None
        return

    headline = json.loads(artifact.read_text(encoding="utf-8"))["headline"]
    assert body["p99_ms"] == headline["p99_ms"]
    assert body["p99_worst_ms"] == headline["p99_ms_worst"]
    # the reported worst case can never be better than the median repeat
    assert body["p99_worst_ms"] >= body["p99_ms"]


def test_version_returns_commit(client):
    body = client.get("/version").json()

    assert "commit" in body
    assert "tag" in body
    assert body["build_time"]
    if body["commit"] is not None:
        assert re.fullmatch(r"[0-9a-f]{7,40}", body["commit"])
