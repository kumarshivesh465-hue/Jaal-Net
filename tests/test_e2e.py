"""End-to-end serving tests through the FastAPI app.

These exercise the real code path — request validation, embedding lookup,
contract detection, ONNX inference — not a mocked scorer. They run in the
default (non-integration) suite because the UPI artifacts are small and
committed for local development.

Accounts are taken from artifacts/upi_node_embeddings.npz so the embedding
lookup is real: a cold-start hash embedding would hide a broken store.
"""

import os

import pytest
from fastapi.testclient import TestClient

import config
import inference

UPI_ARTIFACT = config.UPI_MODEL_PATH
needs_upi = pytest.mark.skipif(
    not os.path.isfile(UPI_ARTIFACT),
    reason=f"{UPI_ARTIFACT} missing (run train_upi_model.py)",
)


def _fresh_client() -> TestClient:
    """TestClient with model + embedding caches cleared, so each test loads
    the artifact it expects instead of a previous test's mock entry."""
    inference._MODEL_CACHE.clear()
    inference._EMBEDDING_STORE = None
    from backend import app

    return TestClient(app)


def _upi_accounts() -> list[str]:
    """First two account ids, alphabetically, from the served embedding store."""
    import numpy as np

    data = np.load(config.UPI_EMBEDDINGS_PATH, allow_pickle=False)
    return sorted(str(acc) for acc in data["account_ids"])


@needs_upi
def test_ring_framing_scores_block():
    """A RING-001 style framing (known mule hub -> cash-out) must block."""
    with _fresh_client() as client:
        body = {
            "txn_id": "UPI-e2e-ring-0001",
            "sender": "L***7350",
            "receiver": "H***3681",
            "amount": 45000.00,
            "origin_balance_error": -8.5,
            "dest_balance_error": -5.2,
            "tx_type": "TRANSFER",
            "velocity_10min": 4,
            "device_change": True,
            "ip_risk": 0.75,
        }
        r = client.post("/score", json=body)

    assert r.status_code == 200
    payload = r.json()
    assert payload["score"] >= 90
    assert payload["action"] == "BLOCK"


@needs_upi
def test_benign_pair_scores_allow():
    """Two benign accounts with benign edge features must not be blocked."""
    sender, receiver = _upi_accounts()[:2]
    with _fresh_client() as client:
        body = {
            "txn_id": "UPI-e2e-benign-0001",
            "sender": sender,
            "receiver": receiver,
            "amount": 1200.00,
            "origin_balance_error": 0.0,
            "dest_balance_error": 0.0,
            "tx_type": "PAYMENT",
            "velocity_10min": 0,
            "device_change": False,
            "ip_risk": 0.0,
        }
        r = client.post("/score", json=body)

    assert r.status_code == 200
    payload = r.json()
    assert payload["score"] <= 30
    assert payload["action"] == "ALLOW"


def test_legacy_payload_accepted():
    """A PaySim-only payload (no UPI fields) stays valid; ScoreRequest
    defaults fill the UPI triple in."""
    sender, receiver = _upi_accounts()[:2]
    with _fresh_client() as client:
        body = {
            "txn_id": "UPI-e2e-legacy-0001",
            "sender": sender,
            "receiver": receiver,
            "amount": 999.00,
            "origin_balance_error": -1.0,
            "dest_balance_error": -1.0,
            "tx_type": "CASH_IN",
        }
        r = client.post("/score", json=body)

    assert r.status_code == 200
    payload = r.json()
    assert 0 <= payload["score"] <= 100
    assert payload["action"] in config.ACTIONS
    assert payload["latency_ms"] > 0
